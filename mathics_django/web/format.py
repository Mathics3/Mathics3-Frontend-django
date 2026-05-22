"""
Format Mathics3 objects
"""

from typing import Dict, Final

from mathics.core.atoms import String
from mathics.core.systemsymbols import (
    SymbolAborted,
    SymbolFailed,
    SymbolInterpretationBox,
    SymbolOutputForm,
    SymbolStandardForm,
    SymbolTeXForm,
)
from mathics.format.box import format_element

# Maps a Form to a kind of html format.
# text is the usual text-kind of output.
# LaTeX is handled by MathJaX display mode $$ $$
# MathML could be tagged differently too.
FORM_TO_HTML_TAG_FORMAT: Final[Dict[str, str]] = {
    "System`FullForm": "text",
    "System`InputForm": "text",
    # "System`MathMLForm": "MathML",
    "System`OutputForm": "text",
    "System`TeXForm": "LaTeX",
    "System`String": "text",
}


def safe_html_string(value):
    """
    Escape characters in the
    """
    # TODO: check why the escaped characters are converted back to valid
    # HTML code and processed.
    return value  # mark_safe(escape_html(value))


def format_output(evaluation, expr, html_tag_format=None):
    """
    Handle unformatted output using the *specific* capabilities \
    of mathics-django.

    evaluation.py format_output() from which this was derived is \
    similar but it can't make use of a front-ends \
    specific capabilities.
    """

    if html_tag_format is None:
        html_tag_format = evaluation.format

    if html_tag_format == "unformatted":
        evaluation.exc_result = None
        return expr

    if isinstance(html_tag_format, dict):
        return dict(
            (k, evaluation.format_output(expr, f)) for k, f in html_tag_format.items()
        )

    if expr is SymbolAborted:
        return "$Aborted"
    elif expr is SymbolFailed:
        return "$Failed"

    # For some expressions, we want formatting to be different.
    # In particular for FullForm and InputForm output, we don't want
    # MathML, we want
    # plain-ol' text so we can cut and paste that.
    expr_type = expr.get_head_name()
    if expr_type in FORM_TO_HTML_TAG_FORMAT:
        # For these forms, we strip off the outer "Form" part
        html_tag_format = FORM_TO_HTML_TAG_FORMAT[expr_type]

    # This part is similar to mathics.core.evaluation.format_output().
    if html_tag_format == "text":
        boxed = format_element(expr, evaluation, SymbolOutputForm)
        result = f'"{boxed.to_text()}"'

        return safe_html_string(result)
    elif html_tag_format == "xml":
        boxed = format_element(expr, evaluation, SymbolStandardForm)
        if (
            hasattr(boxed, "head")
            and boxed.head is SymbolInterpretationBox
            and (box_value := boxed.elements[0].value).startswith('"<math ')
        ):
            # FIXME: [1:-1] is to strip quotes.
            # We should probably address a long-standing mistake where strings
            # have quotes in them.
            return box_value[1:-1]

        # This can happen.
        result = (
            '<math display="block">'
            f"{boxed.to_mathml(evaluation=evaluation)}"
            "</math>"
        )
        return safe_html_string(result)
    elif html_tag_format == "LaTeX":
        boxed = format_element(expr, evaluation, SymbolTeXForm)
        if hasattr(boxed, "head") and boxed.head is SymbolInterpretationBox:
            # FIXME: [1:-1] is to strip quotes.
            # We should probably address a long-standing mistake where strings
            # have quotes in them.
            box_str_sans_quotes = boxed.elements[0].value[1:-1]
            render_TeXForm_expr = evaluation.parse("Settings`$RenderTeXForm")
            render_TeXForm = render_TeXForm_expr.evaluate(evaluation).to_python()
            if render_TeXForm:
                box_str_sans_quotes = f"$${box_str_sans_quotes}$$"
            return box_str_sans_quotes

        # THINK ABOUT: This probably no longer happens
        if isinstance(boxed, String):
            result = boxed.to_text()
        else:
            result = boxed.to_tex(evaluation=evaluation)
        return safe_html_string(result)

    raise ValueError
