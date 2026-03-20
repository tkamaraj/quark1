
#
# Provides the parser for the interpreter.
#

import typing as ty

import parser.internals as pint
import utils.err_codes as uerr
import utils.gen as ugen
import utils.debug as udeb


class Parser:
    def __init__(self) -> None:
        pass

    def _get_unquoted_tok(self, ln: str, start: int) -> pint.Tok | pint.SpChr:
        idx = start

        for char in ln[start :]:
            if char.isspace():
                break
            idx += 1

        val = ln[start : idx]

        # Special characters
        if val in pint.SP_CHRS:
            return pint.SpChr(
                val=val,
                start=start,
                end=idx
            )

        return pint.Tok(
            val=val,
            quoted=False,
            quote_typ=None,
            start=start,
            end=idx
        )

    def _get_quoted_tok(self, ln: str, start: int, quote: str) \
            -> pint.Tok | int:
        # Exclude the opening quote from the index
        elem_start = idx = start + 1
        prev_chr = None

        for char in ln[elem_start :]:
            # Before the if statement to include the closing quote in the index
            idx += 1
            if char == quote and prev_chr != "\\":
                break
            prev_chr = char
        else:
            ugen.err_Q(f"No closing quote at position {idx}")
            return uerr.ERR_NO_CLOSING_QUOTE

        return pint.Tok(
            # Do not include the closin quote in the value
            ln[elem_start : idx - 1],
            quoted=True,
            quote_typ=quote,
            start=start,
            end=idx
        )

    def _get_nxt_tok(self, ln: str, start: int) \
            -> pint.Tok | pint.SpChr | int | None:
        tok: pint.Tok | pint.SpChr | int | None

        # Encountered whitespace
        if ln[start].isspace():
            return None

        if ln[start] not in pint.QUOTES:
            tok = self._get_unquoted_tok(ln, start)
        else:
            tok = self._get_quoted_tok(ln, start, ln[start])

        if isinstance(tok, int):
            return tok

        return tok

    def _reslv_esc_chrs(self, tok: pint.Tok | pint.SpChr) \
            -> pint.Tok | pint.SpChr | int:
        reslvd_tok_val = []
        tok_val_len = len(tok.val)
        skip = 0
        escd_hyphen = False

        if isinstance(tok, pint.SpChr):
            return tok

        for i, char in enumerate(tok.val):
            if skip:
                skip -= 1
                continue

            if char != "\\":
                reslvd_tok_val.append(char)
                continue
            if i == tok_val_len - 1:
                ugen.err_Q(f"Lone backslash at position {tok.start + i}")
                return uerr.ERR_LONE_B_SLASH

            tmp = pint.ESC_CHR_MAP.get("\\" + tok.val[i + 1])
            if tmp is None:
                reslvd_tok_val.append(tok.val[i + 1])
            else:
                reslvd_tok_val.append(tmp)
            skip += 1

            if not i and tok.val[i + 1] == "-":
                escd_hyphen = True

        return pint.Tok(
            val="".join(reslvd_tok_val),
            quoted=tok.quoted,
            quote_typ=tok.quote_typ,
            start=tok.start,
            end=tok.end,
            escd_hyphen=escd_hyphen
        )

    def lex(self, ln: str) -> list[pint.Tok | pint.SpChr] | int:
        idx = 0
        ln_len = len(ln)
        tok_list = []
        tok_list_reslvd = []

        while idx < len(ln):
            tok = self._get_nxt_tok(ln, idx)
            # Encountered whitespace
            if tok is None:
                idx += 1
                continue
            # Encountered errors
            elif isinstance(tok, int):
                return tok

            tok_list.append(tok)
            idx += tok.end - tok.start

        for tok in tok_list:
            reslvd_tok = self._reslv_esc_chrs(tok)
            if isinstance(reslvd_tok, int):
                return reslvd_tok
            tok_list_reslvd.append(reslvd_tok)

        return tok_list_reslvd

    def parse(self, ln: str) -> \
            ty.Generator[tuple[list[pint.Tok], pint.SpChr], None, int | None]:
        to_yield: list[pint.Tok]

        to_yield = []
        toks = self.lex(ln)
        if isinstance(toks, int):
            return toks

        for tok in toks:
            if isinstance(tok, pint.SpChr):
                yield (to_yield, tok)
                to_yield = []
                continue
            to_yield.append(tok)

        # This does NOT account for whitespace at the end; if needed, improve
        # and uncomment
        # final_sp_chr_start = to_yield[-1].end if to_yield else 0
        # final_sp_chr_end = final_sp_chr_start + 1
        yield (to_yield, pint.SpChr("", -2, -1))

    def test(self, ln: str, start: int) -> None:
        for i in self.parse(ln):
            udeb.pprn(i)

