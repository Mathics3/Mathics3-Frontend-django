"""
Format Mathics3 objects
"""

from typing import Final

from django.utils.html import escape
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
FORM_TO_HTML_TAG_FORMAT: Final[dict[str, str]] = {
    "System`FullForm": "text",
    "System`InputForm": "text",
    # "System`MathMLForm": "MathML",
    "System`OutputForm": "text",
    "System`TeXForm": "LaTeX",
    "System`String": "text",
}


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
    expr_head = expr.get_head_name()

    if expr_head in FORM_TO_HTML_TAG_FORMAT:
        # For these forms, we strip off the outer "Form" part
        html_tag_format = FORM_TO_HTML_TAG_FORMAT[expr_head]

    # This part is similar to mathics.core.evaluation.format_output().
    if html_tag_format == "text":
        boxed = format_element(expr, evaluation, SymbolOutputForm)
        return f'"{boxed.to_text()}"'

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
        return (
            '<math display="block">'
            f"{boxed.to_mathml(evaluation=evaluation)}"
            "</math>"
        )
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
        return result

    raise ValueError


def format_information_data(expr, evaluation):
    """
    Format an InformationData expression as an HTML definition list.

    InformationData contains an Association with keys (dt) and values (dd).
    """
    if not expr.elements or len(expr.elements) == 0:
        return "<dl></dl>"

    # The Association is the first element
    association = expr.elements[0]

    # Check if it's an Association by head name
    if (
        not hasattr(association, "get_head_name")
        or association.get_head_name() != "System`Association"
    ):
        return "<dl></dl>"

    dl_content = []

    # Iterate through the Association elements (key-value pairs)
    if hasattr(association, "elements"):
        for rule in association.elements:
            # Rules are typically Rule[key, value]
            if hasattr(rule, "get_head_name") and rule.get_head_name() == "System`Rule":
                if len(rule.elements) >= 2:
                    key = rule.elements[0]
                    value = rule.elements[1]

                    # Format the key as text
                    key_text = format_element(
                        key, evaluation, SymbolOutputForm
                    ).to_text()

                    # Format the value (recursively through format_output)
                    value_formatted = evaluation.format_output(value, evaluation.format)

                    dl_content.append(f"<dt>{escape(key_text)}</dt>")
                    dl_content.append(f"<dd>{value_formatted}</dd>")

    return "<dl>\n" + "\n".join(dl_content) + "\n</dl>"


def format_information_data_grid(expr, evaluation):
    """
    Format an InformationDataGrid expression.

    InformationDataGrid contains a list of strings representing symbol names.
    """
    if not expr.elements:
        return ""

    items = []
    for element in expr.elements:
        if isinstance(element, String):
            items.append(escape(element.value))
        else:
            formatted = format_element(element, evaluation, SymbolOutputForm).to_text()
            items.append(escape(formatted))

    # Return a simple formatted list or table of items
    return (
        "<div class='information-grid'>\n"
        + "\n".join([f"<div>{item}</div>" for item in items])
        + "\n</div>"
    )
