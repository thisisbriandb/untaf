"""Typst Compiler — Compiles .typ source to PDF/PNG.

Uses typst-py for compilation. Manages font paths and package resolution.
"""

import pathlib
import shutil
import tempfile

import typst


_GLOBAL_PKG_PATH: pathlib.Path | None = None


def _setup_package_cache(typst_lib_dir: pathlib.Path) -> pathlib.Path:
    """Set up local Typst package resolution for the cv-engine library (cached singleton)."""
    global _GLOBAL_PKG_PATH
    if _GLOBAL_PKG_PATH is not None and _GLOBAL_PKG_PATH.exists():
        return _GLOBAL_PKG_PATH

    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="cv-engine-pkg-"))

    # Read version from typst.toml
    import tomllib
    toml_path = typst_lib_dir / "typst.toml"
    if toml_path.exists():
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        version = data.get("package", {}).get("version", "0.1.0")
        name = data.get("package", {}).get("name", "cv-engine")
    else:
        version = "0.1.0"
        name = "cv-engine"

    # Create package directory structure
    pkg_dir = temp_dir / "preview" / name / version
    pkg_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(typst_lib_dir / "lib.typ", pkg_dir / "lib.typ")
    shutil.copy2(typst_lib_dir / "typst.toml", pkg_dir / "typst.toml")

    # Fontawesome est vendu dans le dépôt : sans lui, Typst le télécharge à
    # chaque démarrage sur packages.typst.org, et un réseau filtré faisait
    # échouer tout CV mis en page — le pack repartait alors avec l'original.
    fontawesome_dir = typst_lib_dir / "fontawesome"
    if fontawesome_dir.exists():
        fa_version = "0.6.0"
        fa_toml = fontawesome_dir / "typst.toml"
        if fa_toml.exists():
            fa_version = tomllib.loads(fa_toml.read_text(encoding="utf-8")).get(
                "package", {}).get("version", fa_version)
        fa_dir = temp_dir / "preview" / "fontawesome" / fa_version
        fa_dir.mkdir(parents=True, exist_ok=True)
        for f in fontawesome_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, fa_dir / f.name)

    _GLOBAL_PKG_PATH = temp_dir
    return temp_dir


def _localize_images(typst_source: str, work_dir: pathlib.Path) -> str:
    """Copie les images référencées par chemin absolu (photo) là où Typst les trouve."""
    import re
    for img_path_str in re.findall(r'image\("([^"]+)"', typst_source):
        img_path = pathlib.Path(img_path_str)
        if img_path.is_absolute() and img_path.exists():
            shutil.copy2(img_path, work_dir / img_path.name)
            typst_source = typst_source.replace(img_path_str, img_path.name)
    return typst_source


def compile_typst_to_pdf(
    typst_source: str,
    output_path: pathlib.Path | str | None = None,
    font_dirs: list[pathlib.Path | str] | None = None,
) -> bytes:
    """Compile Typst source string to PDF.

    Args:
        typst_source: Complete Typst source code as string.
        output_path: Optional path to write PDF file. If None, returns bytes only.
        font_dirs: Optional list of directories containing custom fonts.

    Returns:
        PDF file contents as bytes.
    """
    typst_lib_dir = pathlib.Path(__file__).parent / "typst"

    # Write typst source to a temp file
    work_dir = pathlib.Path(tempfile.mkdtemp(prefix="cv-engine-work-"))
    
    typst_source = _localize_images(typst_source, work_dir)
    typst_file = work_dir / "cv.typ"
    typst_file.write_text(typst_source, encoding="utf-8")

    # Setup package cache
    pkg_path = _setup_package_cache(typst_lib_dir)

    # Build font paths
    font_paths = []
    if font_dirs:
        font_paths.extend([pathlib.Path(d) for d in font_dirs])

    # Try to use rendercv_fonts if available
    try:
        import rendercv_fonts
        font_paths.extend(rendercv_fonts.paths_to_font_folders)
    except ImportError:
        pass

    # Compile
    compiler = typst.Compiler(
        root=work_dir,
        font_paths=font_paths,
        package_path=pkg_path,
    )

    pdf_bytes = compiler.compile(input=typst_file, format="pdf")

    # Write to output if path provided
    if output_path is not None:
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

    # Cleanup work dir
    shutil.rmtree(work_dir, ignore_errors=True)

    return pdf_bytes


def compile_typst_to_png(
    typst_source: str,
    output_dir: pathlib.Path | str | None = None,
    font_dirs: list[pathlib.Path | str] | None = None,
) -> list[bytes]:
    """Compile Typst source string to PNG images (one per page).

    Args:
        typst_source: Complete Typst source code as string.
        output_dir: Optional directory to write PNG files.
        font_dirs: Optional list of directories containing custom fonts.

    Returns:
        List of PNG file contents as bytes (one per page).
    """
    typst_lib_dir = pathlib.Path(__file__).parent / "typst"

    work_dir = pathlib.Path(tempfile.mkdtemp(prefix="cv-engine-work-"))
    typst_source = _localize_images(typst_source, work_dir)
    typst_file = work_dir / "cv.typ"
    typst_file.write_text(typst_source, encoding="utf-8")

    pkg_path = _setup_package_cache(typst_lib_dir)

    font_paths = []
    if font_dirs:
        font_paths.extend([pathlib.Path(d) for d in font_dirs])

    try:
        import rendercv_fonts
        font_paths.extend(rendercv_fonts.paths_to_font_folders)
    except ImportError:
        pass

    compiler = typst.Compiler(
        root=work_dir,
        font_paths=font_paths,
        package_path=pkg_path,
    )

    png_bytes_list = compiler.compile(input=typst_file, format="png")
    if not isinstance(png_bytes_list, list):
        png_bytes_list = [png_bytes_list]

    # Write to output dir if provided
    if output_dir is not None:
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for i, png_bytes in enumerate(png_bytes_list):
            (output_dir / f"cv_page_{i + 1}.png").write_bytes(png_bytes)

    shutil.rmtree(work_dir, ignore_errors=True)
    # Le cache de paquets est partagé (singleton) : on ne le détruit pas.

    return png_bytes_list


def compile_typst_to_svg(
    typst_source: str,
    font_dirs: list[pathlib.Path | str] | None = None,
) -> str:
    """Compile Typst source string to SVG string.

    Args:
        typst_source: Complete Typst source code as string.
        font_dirs: Optional list of directories containing custom fonts.

    Returns:
        SVG content as string.
    """
    typst_lib_dir = pathlib.Path(__file__).parent / "typst"

    work_dir = pathlib.Path(tempfile.mkdtemp(prefix="cv-engine-work-"))

    import re
    image_matches = re.findall(r'image\("([^"]+)"', typst_source)
    for img_path_str in image_matches:
        img_path = pathlib.Path(img_path_str)
        if img_path.is_absolute() and img_path.exists():
            dest = work_dir / img_path.name
            shutil.copy2(img_path, dest)
            typst_source = typst_source.replace(img_path_str, img_path.name)

    typst_file = work_dir / "cv.typ"
    typst_file.write_text(typst_source, encoding="utf-8")

    pkg_path = _setup_package_cache(typst_lib_dir)

    font_paths = []
    if font_dirs:
        font_paths.extend([pathlib.Path(d) for d in font_dirs])

    try:
        import rendercv_fonts
        font_paths.extend(rendercv_fonts.paths_to_font_folders)
    except ImportError:
        pass

    compiler = typst.Compiler(
        root=work_dir,
        font_paths=font_paths,
        package_path=pkg_path,
    )

    svg_res = compiler.compile(input=typst_file, format="svg")
    if isinstance(svg_res, list):
        svg_bytes = svg_res[0]
    else:
        svg_bytes = svg_res

    svg_str = svg_bytes.decode("utf-8") if isinstance(svg_bytes, bytes) else str(svg_bytes)

    shutil.rmtree(work_dir, ignore_errors=True)

    return svg_str

