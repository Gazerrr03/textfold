"""Office's formulas (OMML: the equations of Word and PowerPoint files) as LaTeX, for KaTeX: fractions, scripts and
roots, sums and integrals with their limits, brackets, functions, accents and bars, matrices and aligned lines, and
the styles of letters (upright, bold, double-struck). A structure it does not know is read as its text.

latex(element) takes an m:oMath (or anything holding one) as lxml parsed it."""
import re
import unicodedata

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

NARY = {"∑": r"\sum", "∏": r"\prod", "∐": r"\coprod", "∫": r"\int", "∬": r"\iint", "∭": r"\iiint", "∮": r"\oint",
        "∯": r"\oiint", "∰": r"\oiiint", "⋃": r"\bigcup", "⋂": r"\bigcap", "⋁": r"\bigvee", "⋀": r"\bigwedge",
        "⨁": r"\bigoplus", "⨂": r"\bigotimes", "⨀": r"\bigodot", "⨄": r"\biguplus"}
ACCENT = {"\u0302": r"\hat", "\u0303": r"\tilde", "\u0304": r"\bar", "\u0305": r"\overline", "\u0307": r"\dot",
          "\u0308": r"\ddot", "\u20db": r"\dddot", "\u20d7": r"\vec", "\u0301": r"\acute", "\u0300": r"\grave",
          "\u0306": r"\breve", "\u030c": r"\check", "\u20d6": r"\overleftarrow", "\u20e1": r"\overleftrightarrow",
          "^": r"\hat", "~": r"\tilde", "¯": r"\bar", "‾": r"\overline", "→": r"\vec"}
BRACE = {"⏟": r"\underbrace", "⏞": r"\overbrace"}   # a brace under or over its terms
FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth", "log",
         "ln", "lg", "exp", "lim", "liminf", "limsup", "max", "min", "sup", "inf", "det", "dim", "ker", "deg", "gcd",
         "arg", "hom", "Pr"}
FENCE = {"{": r"\{", "}": r"\}", "⟨": r"\langle", "⟩": r"\rangle", "〈": r"\langle", "〉": r"\rangle",
         "‖": r"\|", "∥": r"\|", "⌈": r"\lceil", "⌉": r"\rceil", "⌊": r"\lfloor", "⌋": r"\rfloor",
         "|": "|", "(": "(", ")": ")", "[": "[", "]": "]", "/": "/", "\\": r"\backslash"}
ESCAPE = {"#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&", "_": r"\_", "{": r"\{", "}": r"\}", "\\": r"\backslash ",
          "~": r"\sim ", "^": r"\hat{}",
          # the spaces a formula is set with (\quad, \,): KaTeX does not take them as characters
          "\u2001": r"\quad ", "\u2003": r"\quad ", "\u2002": r"\enspace ", "\u2004": r"\;", "\u2005": r"\:",
          "\u2006": r"\,", "\u2009": r"\,", "\u200a": r"\,", "\u205f": r"\:", "\u00a0": "~"}
# the characters a \text{...} run has to escape (in text mode too, % starts a comment and _ ^ & # $ are errors)
TEXT_ESCAPE = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "%": r"\%", "&": r"\&", "#": r"\#",
               "$": r"\$", "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}"}
STYLE = {"p": r"\mathrm", "b": r"\mathbf", "bi": r"\boldsymbol"}
SCRIPT = {"double-struck": r"\mathbb", "script": r"\mathcal", "fraktur": r"\mathfrak", "sans-serif": r"\mathsf",
          "monospace": r"\mathtt"}


def _val(el, path, default=None):
    """The m:val of the property at path under el (a structure's m:xxxPr), or default when it is not set."""
    found = el.find(path) if el is not None else None
    if found is None:
        return default
    return found.get(M + "val", default)


def _plain(s):
    """Mathematical letters (𝑥, 𝐀, ℝ written as letters of their own) as the letters they are styled from."""
    return "".join(unicodedata.normalize("NFKC", c) if 0x1D400 <= ord(c) <= 0x1D7FF else c for c in s)


def _wrap(s):
    """A script's or a function's base in braces when it is more than one thing."""
    s = s.strip()
    return s if len(s) == 1 or re.fullmatch(r"\\[A-Za-z]+", s) else "{" + s + "}"


def _off(pr, tag):
    """Whether an on/off property is on (present without m:val, or m:val 1, on, true)."""
    v = pr.find(M + tag) if pr is not None else None
    return v is not None and v.get(M + "val", "1") in ("1", "on", "true")


class _Latex:
    def __init__(self):
        self.align = False   # inside an equation array: "&" marks where its lines align

    def kids(self, el, skip=("Pr",)):
        return "".join(self.of(c) for c in el if isinstance(c.tag, str) and not c.tag.endswith(skip))

    def arg(self, el, tag):
        part = el.find(M + tag)
        return self.kids(part) if part is not None else ""

    def of(self, el):
        tag = el.tag[len(M):] if el.tag.startswith(M) else None
        if tag is None:   # a run of Word's own (w:r) inside a formula, or anything else: its text
            return "".join(self.run_text(t.text or "") for t in el.iter(M + "t", "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
        do = getattr(self, "do_" + tag, None)
        return do(el) if do else self.kids(el)

    def run_text(self, s, style=None, scr=None, normal=False):
        s = _plain(s)
        if normal:
            # one pass, so the braces of \textbackslash{} are not escaped again
            return r"\text{" + "".join(TEXT_ESCAPE.get(c, c) for c in s) + "}"
        out = "".join("&" if c == "&" and self.align else ESCAPE.get(c, c) for c in s)
        if out.strip() in FUNCS:
            return "\\" + out.strip() + " "
        cmd = SCRIPT.get(scr) or STYLE.get(style)
        if cmd and re.search(r"[A-Za-z]", out):   # (an upright "=" or "(" is as it is)
            return cmd + "{" + out + "}"
        return out

    def do_r(self, el):
        pr = el.find(M + "rPr")
        style, scr = _val(pr, M + "sty"), _val(pr, M + "scr")
        normal = pr is not None and pr.find(M + "nor") is not None
        return "".join(self.run_text(t.text or "", style, scr, normal) for t in el.iter(M + "t"))

    def do_f(self, el):
        num, den, kind = self.arg(el, "num"), self.arg(el, "den"), _val(el.find(M + "fPr"), M + "type", "bar")
        if kind in ("lin", "skw"):
            return f"{_wrap(num)}/{_wrap(den)}"
        if kind == "noBar":   # (\genfrac, which says it best, latex2mathml cannot read)
            return "{" + num + r" \atop " + den + "}"
        return r"\frac{" + num + "}{" + den + "}"

    def do_sSub(self, el):
        return _wrap(self.arg(el, "e")) + "_{" + self.arg(el, "sub") + "}"

    def do_sSup(self, el):
        return _wrap(self.arg(el, "e")) + "^{" + self.arg(el, "sup") + "}"

    def do_sSubSup(self, el):
        return _wrap(self.arg(el, "e")) + "_{" + self.arg(el, "sub") + "}^{" + self.arg(el, "sup") + "}"

    def do_sPre(self, el):
        return "{}_{" + self.arg(el, "sub") + "}^{" + self.arg(el, "sup") + "}" + _wrap(self.arg(el, "e"))

    def do_rad(self, el):
        deg = "" if _off(el.find(M + "radPr"), "degHide") else self.arg(el, "deg").strip()
        return r"\sqrt" + (f"[{deg}]" if deg else "") + "{" + self.arg(el, "e") + "}"

    def do_nary(self, el):
        pr = el.find(M + "naryPr")
        op = NARY.get(_val(pr, M + "chr", "∫"), _val(pr, M + "chr", "∫"))
        if _val(pr, M + "limLoc") == "undOvr" and op in (r"\int", r"\iint", r"\iiint", r"\oint"):
            op += r"\limits"
        sub = "" if _off(pr, "subHide") else self.arg(el, "sub").strip()
        sup = "" if _off(pr, "supHide") else self.arg(el, "sup").strip()
        return op + (f"_{{{sub}}}" if sub else "") + (f"^{{{sup}}}" if sup else "") + " " + self.arg(el, "e")

    def do_d(self, el):
        pr = el.find(M + "dPr")
        beg, end, sep = _val(pr, M + "begChr", "("), _val(pr, M + "endChr", ")"), _val(pr, M + "sepChr", "|")
        es = el.findall(M + "e")
        only = [c for c in es[0] if isinstance(c.tag, str) and not c.tag.endswith("Pr")] if len(es) == 1 else []
        if (beg, end) == ("(", ")") and len(only) == 1 and only[0].tag == M + "f" and _val(only[0].find(M + "fPr"), M + "type") == "noBar":
            return r"\binom{" + self.arg(only[0], "num") + "}{" + self.arg(only[0], "den") + "}"   # n over k in brackets
        parts = [self.kids(e) for e in es]
        inner = f" {FENCE.get(sep, sep)} ".join(parts)
        return r"\left" + (FENCE.get(beg, beg) if beg else ".") + " " + inner + r" \right" + (FENCE.get(end, end) if end else ".")

    def do_func(self, el):
        name = self.arg(el, "fName").strip()
        return name + ("" if name.endswith((" ", "}")) else " ") + self.arg(el, "e")

    def do_limLow(self, el):
        lim = self.arg(el, "lim")
        if lim.strip() in BRACE:   # a brace written as a limit under its terms (as pandoc writes \underbrace)
            return BRACE[lim.strip()] + "{" + self.arg(el, "e") + "}"
        return _wrap(self.arg(el, "e")) + "_{" + lim + "}"

    def do_limUpp(self, el):
        lim = self.arg(el, "lim")
        if lim.strip() in BRACE:
            return BRACE[lim.strip()] + "{" + self.arg(el, "e") + "}"
        return r"\overset{" + lim + "}{" + self.arg(el, "e") + "}"

    def do_acc(self, el):
        ch = _val(el.find(M + "accPr"), M + "chr", "\u0302")
        cmd = ACCENT.get(ch)
        return (cmd + "{" if cmd else r"\overset{" + ch + "}{") + self.arg(el, "e") + "}"

    def do_bar(self, el):
        top = _val(el.find(M + "barPr"), M + "pos", "bot") == "top"
        return (r"\overline{" if top else r"\underline{") + self.arg(el, "e") + "}"

    def do_groupChr(self, el):
        pr = el.find(M + "groupChrPr")
        ch, pos = _val(pr, M + "chr", "⏟"), _val(pr, M + "pos", "bot")
        e = self.arg(el, "e")
        if ch == "⏟":
            return r"\underbrace{" + e + "}"
        if ch == "⏞":
            return r"\overbrace{" + e + "}"
        return (r"\overset{" if pos == "top" else r"\underset{") + ch + "}{" + e + "}"

    def do_borderBox(self, el):
        return r"\boxed{" + self.arg(el, "e") + "}"

    def do_phant(self, el):
        return (r"\phantom{" + self.arg(el, "e") + "}") if _val(el.find(M + "phantPr"), M + "show", "1") in ("0", "off", "false") else self.arg(el, "e")

    def do_eqArr(self, el):
        was, self.align = self.align, True
        rows = [self.kids(e) for e in el.findall(M + "e")]
        self.align = was
        # an array, its columns right and left as aligned's are (latex2mathml reads no aligned or gathered)
        n = max(r.count("&") for r in rows) + 1 if rows else 1
        spec = ("rl" * n)[:n] if n > 1 else "c"
        return r"\begin{array}{" + spec + "}" + r" \\ ".join(rows) + r"\end{array}"

    def do_m(self, el):
        was, self.align = self.align, False
        rows = [" & ".join(self.kids(e) for e in mr.findall(M + "e")) for mr in el.findall(M + "mr")]
        self.align = was
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"

    def do_oMathPara(self, el):
        return r" \\ ".join(self.of(m) for m in el.findall(M + "oMath"))


def latex(el):
    """An m:oMath (or an m:oMathPara, or anything holding one) as LaTeX, its spacing tidied."""
    s = _Latex().of(el)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()
