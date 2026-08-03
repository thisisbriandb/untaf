{% if design.header_style == "banner" or design.colors.banner_bg %}
#block(
  fill: {{ design.colors.banner_bg.as_rgb() }},
  width: 100%,
  inset: (x: 20pt, y: 18pt),
  radius: 4pt,
)[
  #grid(
    columns: (1fr, auto),
    column-gutter: 16pt,
    align: (left + horizon, right + horizon),
    [
      #set text(fill: rgb(255, 255, 255))
      {% if cv.name %}
      #text(weight: "extrabold", size: 17pt)[{{ cv.name }}] \
      {% endif %}
      {% if cv.headline %}
      #v(4pt)
      #text(weight: "medium", size: 9.5pt, fill: rgb(255, 255, 255).darken(5%))[{{ cv.headline }}] \
      {% endif %}
      #v(8pt)
      #text(size: 8.5pt, fill: rgb(255, 255, 255).darken(5%))[
        {% for connection in cv._connections %}
        {{ connection }}{% if not loop.last %} #h(5pt) • #h(5pt) {% endif %}
        {% endfor %}
      ]
    ],
    {% if cv.photo %}
    [
      #box(
        clip: true,
        radius: 28pt,
        stroke: 2pt + rgb(255, 255, 255),
        image("{{ cv.photo }}", width: 2.2cm, height: 2.2cm, fit: "cover")
      )
    ]
    {% endif %}
  )
]
#v(14pt)
{% else %}
{% macro image() %}
#pad(left: {{ design.header.photo_space_left }}, right: {{ design.header.photo_space_right }}, image("{{ cv.photo }}", width: {{ design.header.photo_width }}))
{% endmacro %}

{% if cv.photo %}
#grid(
{% if design.header.photo_position == "left" %}
  columns: (auto, 1fr),
{% else %}
  columns: (1fr, auto),
{% endif %}
  column-gutter: 0cm,
  align: horizon + left,
{% if design.header.photo_position == "left" %}
  [{{ image() }}],
  [
{% else %}
  [
{% endif %}
{% endif %}
{% if cv.name %}
= {{ cv.name }}
{% endif %}

{% if cv.headline %}
  #headline([{{ cv.headline }}])

{% endif %}
#connections(
{% for connection in cv._connections %}
  [{{ connection }}],
{% endfor %}
)
{% if cv.photo %}
{% if design.header.photo_position == "left" %}
  ]
)
{% else %}
  ],
  [{{ image() }}],
)
{% endif %}
{% endif %}
{% endif %}
