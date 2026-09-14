"""Tkinter GUI for certsign."""
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import SigningError, generate_self_signed_pfx
from .signers import SIGNERS, default_output_path

CERT_FILETYPES = [("PKCS#12 certificate", "*.pfx *.p12"), ("All files", "*.*")]
TARGET_FILETYPES = [
    ("Signable files", "*.exe *.jar *.pdf *.png *.jpg *.jpeg *.docx *.txt"),
    ("All files", "*.*"),
]


class CertSignApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CertSign - Datei-Signierung mit selbstsigniertem Zertifikat")
        self.geometry("640x420")
        self.resizable(False, False)

        self.pfx_path = tk.StringVar()
        self.pfx_password = tk.StringVar()
        self.target_path = tk.StringVar()
        self.output_path = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        cert_frame = ttk.LabelFrame(self, text="1. Zertifikat")
        cert_frame.pack(fill="x", **pad)

        row = ttk.Frame(cert_frame)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Entry(row, textvariable=self.pfx_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Durchsuchen...", command=self._pick_cert).pack(side="left", padx=6)
        ttk.Button(row, text="Neues Zertifikat erzeugen...", command=self._gen_cert).pack(side="left")

        pwd_row = ttk.Frame(cert_frame)
        pwd_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(pwd_row, text="Passwort:").pack(side="left")
        ttk.Entry(pwd_row, textvariable=self.pfx_password, show="*").pack(side="left", fill="x", expand=True, padx=6)

        target_frame = ttk.LabelFrame(self, text="2. Zu signierende Datei")
        target_frame.pack(fill="x", **pad)
        row2 = ttk.Frame(target_frame)
        row2.pack(fill="x", padx=8, pady=4)
        ttk.Entry(row2, textvariable=self.target_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="Durchsuchen...", command=self._pick_target).pack(side="left", padx=6)

        out_frame = ttk.LabelFrame(self, text="3. Ausgabedatei")
        out_frame.pack(fill="x", **pad)
        row3 = ttk.Frame(out_frame)
        row3.pack(fill="x", padx=8, pady=4)
        ttk.Entry(row3, textvariable=self.output_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row3, text="Durchsuchen...", command=self._pick_output).pack(side="left", padx=6)

        self.sign_btn = ttk.Button(self, text="Signieren", command=self._sign)
        self.sign_btn.pack(pady=10)

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pick_cert(self):
        path = filedialog.askopenfilename(title="Zertifikat waehlen", filetypes=CERT_FILETYPES)
        if path:
            self.pfx_path.set(path)

    def _pick_target(self):
        path = filedialog.askopenfilename(title="Datei waehlen", filetypes=TARGET_FILETYPES)
        if path:
            self.target_path.set(path)
            self._suggest_output()

    def _pick_output(self):
        path = filedialog.asksaveasfilename(title="Ausgabedatei waehlen")
        if path:
            self.output_path.set(path)

    def _suggest_output(self):
        target = self.target_path.get()
        if not target:
            return
        ext = Path(target).suffix.lower()
        kind = SIGNERS.get(ext, ("detached", None))[0]
        self.output_path.set(default_output_path(target, kind))

    def _gen_cert(self):
        dialog = tk.Toplevel(self)
        dialog.title("Neues Zertifikat erzeugen")
        dialog.geometry("380x200")
        dialog.transient(self)
        dialog.grab_set()

        cn = tk.StringVar(value="MySelfSignedCert")
        pw = tk.StringVar()
        out = tk.StringVar(value=str(Path.home() / "certsign.pfx"))

        ttk.Label(dialog, text="Common Name (Herausgeber):").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Entry(dialog, textvariable=cn).pack(fill="x", padx=10)

        ttk.Label(dialog, text="Passwort:").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Entry(dialog, textvariable=pw, show="*").pack(fill="x", padx=10)

        out_row = ttk.Frame(dialog)
        out_row.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Entry(out_row, textvariable=out).pack(side="left", fill="x", expand=True)

        def do_generate():
            if not pw.get():
                messagebox.showerror("Fehler", "Bitte ein Passwort angeben.")
                return
            try:
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    generate_self_signed_pfx(out.get(), pw.get(), cn.get(), tmp)
                self.pfx_path.set(out.get())
                self.pfx_password.set(pw.get())
                self._log(f"Neues Zertifikat erzeugt: {out.get()}")
                dialog.destroy()
            except SigningError as e:
                messagebox.showerror("Fehler", str(e))

        ttk.Button(dialog, text="Erzeugen", command=do_generate).pack(pady=15)

    def _sign(self):
        pfx = self.pfx_path.get()
        pw = self.pfx_password.get()
        target = self.target_path.get()
        out = self.output_path.get()

        if not pfx or not pw or not target or not out:
            messagebox.showerror("Fehler", "Bitte Zertifikat, Passwort, Quelldatei und Ausgabedatei angeben.")
            return

        ext = Path(target).suffix.lower()
        if ext not in SIGNERS:
            messagebox.showerror("Fehler", f"Dateityp '{ext}' wird nicht unterstuetzt.")
            return

        kind, signer_fn = SIGNERS[ext]
        self.sign_btn.configure(state="disabled")
        self._log(f"Signiere {target} ({kind}) ...")

        def worker():
            try:
                signer_fn(pfx, pw, target, out)
                self.after(0, lambda: self._on_done(True, out, kind))
            except SigningError as e:
                self.after(0, lambda: self._on_done(False, str(e), kind))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, ok, message, kind):
        self.sign_btn.configure(state="normal")
        if ok:
            if kind == "detached":
                note = " (separate .sig-Datei, da dieses Format kein natives Signaturformat hat)"
            elif kind == "embedded":
                note = " (Signatur wurde ans Ende der Datei angehaengt, kein separates File noetig)"
            else:
                note = ""
            self._log(f"Fertig: {message}{note}")
            messagebox.showinfo("Erfolg", f"Signiert: {message}{note}")
        else:
            self._log(f"Fehler: {message}")
            messagebox.showerror("Fehler", message)


def main():
    app = CertSignApp()
    app.mainloop()


if __name__ == "__main__":
    main()
