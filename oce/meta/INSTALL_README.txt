OHJE: Uusien meta-moduulien asennus (MetacogCalib + MythGuard)

1) Pura tämä zip mihin tahansa.
2) Kopioi tiedostot projektissasi polkuun:
   <projekti>/oce/meta/metacog_calib.py
   <projekti>/oce/meta/myth_guard.py

3) Avaa <projekti>/oce/oce_core.py ja lisää importit muiden meta-tuontien joukkoon:
   from .meta.metacog_calib import MetacogCalib
   from .meta.myth_guard import MythGuard

4) Lisää run_oce-funktion meta-osioon (CFLEthics/EvidenceEngine jälkeen):
   metacog = MetacogCalib().assess(session_ctx)
   myth = MythGuard().analyze(md, session_ctx)

5) Lisää ne summary-sanastoon:
   "metacog": metacog,
   "mythguard": myth

6) Lisää markdown-raportin META-lohkoon tuloste:
   text += f"- Metacog: {summary['metacog']}\n- MythGuard: {summary['mythguard']}\n"

7) (Valinnainen demo) Avaa oce/demo.py ja lisää ctx:iin:
   "self_prob": 0.8
   sekä user_textiin jokin absoluuttinen ilmaus (esim. "always"), jotta MythGuard aktivoituu.

8) Aja: python -m oce.demo
