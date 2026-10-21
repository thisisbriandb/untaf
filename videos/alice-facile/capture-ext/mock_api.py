"""API factice pour filmer la vraie extension (profil de démo, aucune donnée réelle)."""
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
CV = Path(__file__).resolve().parents[1] / "assets/cv/cv-camille.pdf"
JOB = {"job_id": "job-1", "title": "Alternance — Chargé·e de marketing digital", "company_name": "Atelier Nord", "pack_ready": True, "status": "pack_ready"}
PROFILE = {"full_name": "Camille Martin", "first_name": "Camille", "last_name": "Martin", "email": "camille.martin@exemple.fr",
           "contact_email": "camille.martin@reponses.alice-agent.fr", "phone": "06 12 34 56 78", "city": "Lyon",
           "linkedin_url": "", "github_url": "", "website_url": "", "headline": "Alternance — Marketing digital"}
LETTER = ("Madame, Monsieur,\n\nVotre atelier fait du contenu un levier de croissance : c'est ce que j'ai appris à piloter "
          "en stage chez Maison Calme, où mes campagnes e-mailing ont gagné 18 % de taux d'ouverture. Je souhaite poursuivre en alternance "
          "à vos côtés dès septembre.\n\nCamille Martin")
class H(BaseHTTPRequestHandler):
    def _h(self, code=200, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
    def do_OPTIONS(self): self._h(204); self.end_headers()
    def _json(self, o): self._h(); self.end_headers(); self.wfile.write(json.dumps(o).encode())
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/me": return self._json({"candidate_id": "demo-cand", "email": PROFILE["email"]})
        if p.endswith("/extension/match"): return self._json(JOB)
        if p.endswith("/extension/profile"): return self._json(PROFILE)
        if p.endswith("/state"): return self._json({"letter": {"body": LETTER}})
        if p.endswith("/cv"):
            self._h(200, "application/pdf"); self.send_header("Content-Disposition", 'attachment; filename="CV_Camille_Martin.pdf"')
            self.end_headers(); return self.wfile.write(CV.read_bytes())
        self._json({})
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        p = self.path
        if p.endswith("/extension/answers"):
            ans = []
            for q in body.get("questions", []):
                lab = q.get("label", "").lower()
                if "disponib" in lab: continue  # laissé au candidat : en orange
                if "niveau" in lab or "études" in lab: ans.append({"id": q["id"], "value": "Bac +3"})
            return self._json({"answers": ans})
        self._json({})
    def log_message(self, *a): sys.stderr.write(self.path + "\n")
ThreadingHTTPServer(("127.0.0.1", 8766), H).serve_forever()
