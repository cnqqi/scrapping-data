"""Deteksi lokasi lowongan: luar negeri vs Indonesia, dan prioritas wilayah.

Prioritas wilayah = Jawa Tengah, Solo Raya, dan DI Yogyakarta.
Loker di luar prioritas tapi tetap di Indonesia (Jabodetabek, Surabaya, dll)
tidak dibuang — hanya diberi peringkat di bawah wilayah prioritas.
"""

import re

# Penanda lokasi luar negeri / remote antarnegara.
FOREIGN_PATTERNS = [
    # Singapura & Malaysia
    r"\bsingapore\b", r"\bsingapura\b", r"\bmalaysia\b", r"\bkuala lumpur\b",
    # Asia Tenggara & Asia
    r"\bphilippines\b", r"\bmanila\b", r"\bthailand\b", r"\bbangkok\b",
    r"\bvietnam\b", r"\bhanoi\b", r"\bho chi minh\b", r"\bmyanmar\b",
    r"\bcambodia\b", r"\blaos\b", r"\bbrunei\b", r"\bgambodia\b",
    r"\bindia\b", r"\bindian\b", r"\bmumbai\b", r"\bdelhi\b",
    r"\bbangalore\b", r"\bbengaluru\b",
    # Asia Timur
    r"\btokyo\b", r"\bjapan\b", r"\bjepang\b", r"\bkorea\b", r"\bseoul\b",
    r"\btaiwan\b", r"\btaipei\b", r"\bhong kong\b", r"\bmakau\b",
    r"\bshanghai\b", r"\bbeijing\b", r"\bchina\b", r"\bchinese\b",
    # Amerika & Eropa & lain
    r"\bunited states\b", r"\bunited states of america\b", r"\busa\b",
    r"\bnew york\b", r"\bsan francisco\b", r"\bcalifornia\b",
    r"\blondon\b", r"\bunited kingdom\b", r"\bengland\b",
    r"\bgermany\b", r"\bberlin\b", r"\bfrance\b", r"\bparis\b",
    r"\bnetherlands\b", r"\bamsterdam\b", r"\bdubai\b", r"\buae\b",
    r"\bsaudi arabia\b", r"\briyadh\b", r"\bqatar\b", r"\bdoha\b",
    r"\bcanada\b", r"\btoronto\b", r"\bnew zealand\b", r"\baustralia\b",
    r"\bsydney\b", r"\bmelbourne\b",
    # Frasa penempatan luar negeri / remote antarnegara
    r"\bluar negeri\b", r"\bdi luar negeri\b", r"\boverseas\b",
    r"\bwork abroad\b", r"\babroad\b", r"\bremote worldwide\b",
    r"\banywhere in the world\b", r"\bremote overseas\b",
]

# Wilayah prioritas: Jawa Tengah, Solo Raya, DI Yogyakarta.
PRIORITY_PATTERNS = [
    # Jawa Tengah
    r"\bjawa tengah\b", r"\bjawatengah\b", r"\bjateng\b", r"\bcentral java\b",
    r"\bsemarang\b", r"\bmagelang\b", r"\bpurwokerto\b", r"\btegal\b",
    r"\bpekalongan\b", r"\bsalatiga\b", r"\bkudus\b", r"\bpati\b",
    r"\bcilacap\b", r"\bkebumen\b", r"\bpurworejo\b", r"\bwonosobo\b",
    r"\btemanggung\b", r"\bbanjarnegara\b", r"\bpurbalingga\b",
    r"\bbanyumas\b", r"\bbrebes\b", r"\bpemalang\b", r"\bbatang\b",
    r"\bkendal\b", r"\bdemak\b", r"\bjepara\b", r"\brembang\b",
    r"\bblora\b", r"\bgrobogan\b",
    # Solo Raya (Surakarta & sekitarnya)
    r"\bsolo\b", r"\bsurakarta\b", r"\bsoloraya\b", r"\bsolo raya\b",
    r"\bklaten\b", r"\bsukoharjo\b", r"\bboyolali\b", r"\bwonogiri\b",
    r"\bkaranganyar\b", r"\bsragen\b",
    # DI Yogyakarta
    r"\byogyakarta\b", r"\byogya\b", r"\bjogja\b", r"\bjogyakarta\b",
    r"\bdaerah istimewa yogyakarta\b", r"\bsleman\b", r"\bbantul\b",
    r"\bkulon progo\b", r"\bgunungkidul\b", r"\bgunung kidul\b",
]

_FOREIGN_RE = re.compile("|".join(FOREIGN_PATTERNS), re.I)
_PRIORITY_RE = re.compile("|".join(PRIORITY_PATTERNS), re.I)


def is_foreign(location):
    """True bila lokasi jelas di luar negeri / remote antarnegara."""
    if not location:
        return False
    return bool(_FOREIGN_RE.search(location))


def priority_rank(location):
    """0 = wilayah prioritas (Jateng/Solo Raya/Yogyakarta), 1 = Indonesia lain."""
    if not location:
        return 1
    return 0 if _PRIORITY_RE.search(location) else 1