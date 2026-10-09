#!/usr/bin/env python3
"""Video Grabber - graphical interface. Run: python gui.py"""

import asyncio
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import core


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.t = core.Translator("en")
        self.q: queue.Queue = queue.Queue()
        self.items: list = []
        self.session = None  # (page_url, user_agent, cookies) of the last scan
        self.bound: list = []  # (widget, option, key) re-translated on language change

        self.url = tk.StringVar()
        self.wait = tk.IntVar(value=20)
        self.out = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.use_cdp = tk.BooleanVar(value=False)
        self.cdp = tk.StringVar(value="http://localhost:9222")
        self.status = tk.StringVar()

        self.build()
        self.apply_lang()
        self.status.set(self.t("ready"))
        self.root.after(100, self.pump)

    # ---------- layout ----------
    def label(self, parent, key, **kw):
        w = ttk.Label(parent, **kw)
        self.bound.append((w, "text", key))
        return w

    def button(self, parent, key, command, **kw):
        w = ttk.Button(parent, command=command, **kw)
        self.bound.append((w, "text", key))
        return w

    def build(self):
        r = self.root
        r.geometry("920x620")
        r.minsize(760, 520)
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(r)
        top.pack(fill="x", **pad)
        top.columnconfigure(1, weight=1)

        self.label(top, "url_label").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(top, textvariable=self.url)
        entry.grid(row=0, column=1, sticky="ew", padx=6)
        entry.bind("<Return>", lambda e: self.scan())
        entry.focus()
        self.scan_btn = self.button(top, "scan_btn", self.scan)
        self.scan_btn.grid(row=0, column=2)

        self.label(top, "out_label").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.out).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        row1 = ttk.Frame(top)
        row1.grid(row=1, column=2)
        self.button(row1, "browse", self.browse).pack(side="left")
        self.button(row1, "open_folder", self.open_folder).pack(side="left", padx=(4, 0))

        opts = ttk.Frame(r)
        opts.pack(fill="x", **pad)
        self.label(opts, "wait_label").pack(side="left")
        ttk.Spinbox(opts, from_=5, to=300, width=5, textvariable=self.wait).pack(side="left", padx=(4, 16))
        cb = ttk.Checkbutton(opts, variable=self.use_cdp)
        self.bound.append((cb, "text", "use_cdp"))
        cb.pack(side="left")
        ttk.Entry(opts, textvariable=self.cdp, width=24).pack(side="left", padx=6)
        self.lang_box = ttk.Combobox(opts, state="readonly", width=10, values=[core.TEXTS[c]["lang_name"] for c in core.LANGS])
        self.lang_box.current(0)
        self.lang_box.pack(side="right")
        self.lang_box.bind("<<ComboboxSelected>>", self.on_lang)
        self.label(opts, "lang_label").pack(side="right", padx=6)

        self.label(r, "tip", foreground="#666").pack(fill="x", padx=8)

        mid = ttk.Frame(r)
        mid.pack(fill="both", expand=True, **pad)
        cols = ("type", "size", "source", "url")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended", height=8)
        for c, w in zip(cols, (110, 80, 70, 600)):
            self.tree.column(c, width=w, anchor="w", stretch=(c == "url"))
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        actions = ttk.Frame(r)
        actions.pack(fill="x", **pad)
        self.dl_btn = self.button(actions, "download_btn", self.download)
        self.dl_btn.pack(side="left")
        self.button(actions, "select_all", lambda: self.tree.selection_set(self.tree.get_children())).pack(side="left", padx=6)
        self.bar = ttk.Progressbar(actions, maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=8)

        self.label(r, "log_label").pack(anchor="w", padx=8)
        logf = ttk.Frame(r)
        logf.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.logbox = tk.Text(logf, height=8, state="disabled", wrap="word")
        lsb = ttk.Scrollbar(logf, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=lsb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")

        ttk.Label(r, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def apply_lang(self):
        for w, opt, key in self.bound:
            w.configure(**{opt: self.t(key)})
        for c, key in zip(("type", "size", "source", "url"), ("col_type", "col_size", "col_source", "col_url")):
            self.tree.heading(c, text=self.t(key))
        self.root.title(self.t("title"))
        self.refresh_rows()

    def on_lang(self, _e=None):
        self.t.set_lang(core.LANGS[self.lang_box.current()])
        self.apply_lang()

    # ---------- actions ----------
    def browse(self):
        d = filedialog.askdirectory(initialdir=self.out.get() or str(Path.home()))
        if d:
            self.out.set(d)

    def open_folder(self):
        p = Path(self.out.get())
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])

    def log(self, text: str):
        self.q.put(("log", text))

    def progress(self, done: int, total: int):
        self.q.put(("progress", done, total))

    def set_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.dl_btn.configure(state=state)

    def run_bg(self, factory, on_done):
        self.set_busy(True)

        def work():
            try:
                self.q.put(("done", on_done, asyncio.run(factory())))
            except Exception as e:
                self.q.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def scan(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showinfo(self.t("title"), self.t("no_url"))
            return
        if "://" not in url:
            url = "https://" + url
            self.url.set(url)
        cdp = self.cdp.get().strip() if self.use_cdp.get() else None
        self.items, self.session = [], None
        self.refresh_rows()
        self.status.set(self.t("scanning"))
        self.bar.configure(value=0)

        async def job():
            items, ua, cookies = await core.detect(self.t, url, cdp, int(self.wait.get()), self.log)
            return url, items, ua, cookies

        self.run_bg(job, self.on_scanned)

    def on_scanned(self, res):
        url, items, ua, cookies = res
        self.items, self.session = items, (url, ua, cookies)
        self.refresh_rows()
        if items:
            self.status.set(self.t("found_n", n=len(items)))
            self.tree.selection_set(self.tree.get_children()[:1])
        else:
            self.status.set(self.t("ready"))
            self.log(self.t("none"))

    def refresh_rows(self):
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), values=(
                core.label_for(self.t, it), core.human(it["size"]), self.t(it["source"]), it["url"]))

    def download(self):
        sel = [self.items[int(i)] for i in self.tree.selection()]
        if not sel or not self.session:
            messagebox.showinfo(self.t("title"), self.t("no_selection"))
            return
        page_url, ua, cookies = self.session
        out = Path(self.out.get())
        self.status.set(self.t("downloading"))
        self.bar.configure(value=0)

        async def job():
            await core.download_items(self.t, sel, page_url, ua, cookies, out, self.log, self.progress)

        self.run_bg(job, lambda _r: self.status.set(self.t("finished")))

    # ---------- thread -> UI bridge ----------
    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.logbox.configure(state="normal")
                    self.logbox.insert("end", msg[1] + "\n")
                    self.logbox.see("end")
                    self.logbox.configure(state="disabled")
                elif kind == "progress":
                    done, total = msg[1], msg[2]
                    self.bar.configure(value=(done / total * 100) if total else 0)
                    self.status.set(f"{self.t('downloading')} {core.human(done)}" + (f" / {core.human(total)}" if total else ""))
                elif kind == "done":
                    self.set_busy(False)
                    msg[1](msg[2])
                elif kind == "error":
                    self.set_busy(False)
                    self.status.set(self.t("ready"))
                    self.log(self.t("error", err=msg[1]))
        except queue.Empty:
            pass
        self.root.after(100, self.pump)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
