p = "fix_encoding.py"
s = open(p, encoding="utf-8").read()
old_markers = "MARKERS = [\"\u00c3\", \"\u00c2\", \"\u251c\", \"\u00e2\", \"\u252c\", \"\u2500\", \"\u00e4\u252c\"]"
new_markers = "MARKERS = [\"\u00c3\", \"\u00c2\"]"
s = s.replace(old_markers, new_markers)
old_fix = "        step1 = text.encode(\"cp850\").decode(\"utf-8\")\n        step2 = step1.encode(\"latin1\").decode(\"utf-8\")"
new_fix = "        fixed = text.encode(\"latin1\").decode(\"utf-8\")"
s = s.replace(old_fix, new_fix)
old_check = "    if looks_corrupted(step2):\n        return None\n    if step2 == text:\n        return None\n    return step2"
new_check = "    if looks_corrupted(fixed):\n        return None\n    if fixed == text:\n        return None\n    return fixed"
s = s.replace(old_check, new_check)
open(p, "w", encoding="utf-8").write(s)
print("Reemplazos hechos:", old_markers in open(p, encoding="utf-8").read())
print("OK, tamano final:", len(s))
