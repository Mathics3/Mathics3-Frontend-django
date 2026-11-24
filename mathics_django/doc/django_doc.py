# -*- coding: utf-8 -*-
"""
This code is the Django-specific part of the homegrown sphinx documentation.
FIXME: Ditch this and hook into sphinx
"""

import os
import os.path as osp
import pickle
from pathlib import Path

from django.utils.safestring import mark_safe
from mathics.doc.common_doc import (
    DocChapter,
    DocPart,
    DocSection,
    DocSubsection,
    DocTest,
    DocTests,
    DocText,
    Documentation,
    DocumentationEntry,
    get_results_by_test,
    sorted_chapters,
)

from mathics_django.doc.utils import escape_html
from mathics_django.settings import (
    DATA_DIR,
    DOCTEST_LATEX_DATA_PCL,
    get_doctest_html_data_path,
)

DOCTEST_SYSTEM_LATEX_DATA_PCL = os.environ.get(
    "DOCTEST_SYSTEM_LATEX_DATA_PCL",
    osp.join("Data", "doctest_latex_data.pcl"),
)


def get_doctest_latex_data_path(should_be_readable=False, create_parent=False) -> str:
    """Returns a string path where we can find Python Pickle doctest data for LaTeX
    processing.

    If `should_be_readable` is True, the we will check to see whether
    this file is readable (which also means it exists). If not, we'll
    return the `DOCTEST_SYSTEM_DATA_PATH`.

    """
    doc_user_latex_data_pcl = Path(DOCTEST_LATEX_DATA_PCL)
    base_config_dir = doc_user_latex_data_pcl.parent
    if not base_config_dir.is_dir() and create_parent:
        Path("base_config_dir").mkdir(parents=True, exist_ok=True)

    if should_be_readable:
        return (
            DOCTEST_LATEX_DATA_PCL
            if doc_user_latex_data_pcl.is_file()
            else DOCTEST_SYSTEM_LATEX_DATA_PCL
        )
    else:
        return DOCTEST_LATEX_DATA_PCL


# FIXME: remove globalness
doctest_html_data_path = get_doctest_html_data_path(should_be_readable=True)
try:
    with open(doctest_html_data_path, "rb") as doctest_html_data_file:
        doc_data = pickle.load(doctest_html_data_file)
except IOError:
    print(f"Trouble reading Doc file {doctest_html_data_path}")
    doc_data = {}


class DjangoDocElement:
    """
    Adds some HTML functions onto existing Django Document Elements.
    """

    def href(self, ajax=False):
        """Return the URI of the element. If the call is done
        using ajax, the href is a javascript instruction for loading
        the documentation from the corresponding uri."""
        if ajax:
            return f"javascript:loadDoc('{self.get_uri()}')"
        else:
            return f"/doc{self.get_uri()}"

    def get_prev(self):
        return self.get_prev_next()[0]

    def get_next(self):
        return self.get_prev_next()[1]

    def get_collection(self):
        return []

    def get_prev_next(self):
        collection = self.get_collection()
        index = collection.index(self)
        prev = collection[index - 1] if index > 0 else None
        next = collection[index + 1] if index < len(collection) - 1 else None
        return prev, next

    def get_title_html(self):
        """Get the title of the element."""
        # used by web/templatetags/doc.py
        return mark_safe(escape_html(self.title, single_line=True))


class DjangoDocumentation(Documentation, DjangoDocElement):
    def __init__(self):
        super(DjangoDocumentation, self).__init__()
        self.doc_dir = DATA_DIR

        self.load_documentation_sources()
        self.doctest_latex_pcl_path = DOCTEST_LATEX_DATA_PCL
        self.pymathics_doc_loaded = False
        self.doc_data_file = get_doctest_latex_data_path(should_be_readable=True)
        self.title = "Overview"

    def _set_classes(self):
        self.doc_class = DjangoDoc
        self.chapter_class = DjangoDocChapter
        self.guide_section_class = DjangoDocGuideSection
        self.part_class = DjangoDocPart
        self.section_class = DjangoDocSection
        self.subsection_class = DjangoDocSubsection

    def __str__(self):
        return "\n\n\n".join(str(part) for part in self.parts)

    def get_uri(self) -> str:
        """Return the URI of the documentation root."""
        return "/"

    def search(self, query):
        """Handles interactive search in browser."""

        query = query.strip()
        query_parts = [q.strip().lower() for q in query.split()]

        def matches(text):
            text = text.lower()
            return all(q in text for q in query_parts)

        def name_compare_goodness(result_data):
            exact, item = result_data
            name = item.title
            if exact:
                return -4 if name == query else -3

            if name.startswith(query):
                return -2
            if query in name:
                return -1
            lower_name = name.lower()
            if lower_name.startswith(query):
                return 0
            if lower_name in query:
                return 1
            return 2

        def search_sections(section, result):
            for subsection in section.subsections:
                if matches(subsection.title):
                    result.append((subsection.title == query, subsection))
                elif query == subsection.operator:
                    result.append((True, subsection))

        result = []
        for part in self.parts:
            if matches(part.title):
                result.append((False, part))
            for chapter in sorted_chapters(part.chapters):
                if matches(chapter.title):
                    result.append((False, chapter))
                for section in chapter.sections:
                    if matches(section.title):
                        if not isinstance(section, DjangoDocGuideSection):
                            result.append((section.title == query, section))
                    elif query == section.operator:
                        result.append((True, section))
                        continue
                    search_sections(section, result)
                for section in chapter.guide_sections:
                    if matches(section.title):
                        result.append((section.title == query, section))
                    elif query == section.operator:
                        result.append((True, section))
                        continue
                    search_sections(section, result)

        sorted_results = sorted(result, key=name_compare_goodness)
        return sorted_results


class DjangoDoc(DocumentationEntry):
    def _set_classes(self):
        """
        Tells to the initializator the classes to be used to build the items.
        This must be overloaded by the daughter classes.
        """
        self.docTest_collection_class = DjangoDocTests
        self.docTest_class = DjangoDocTest
        self.docText_class = DjangoDocText

    def __str__(self):
        return "\n".join(str(item) for item in self.items)

    def get_tests(self):
        tests = []
        for item in self.items:
            tests.extend(item.get_tests())
        return tests

    def html(self):
        items = [item for item in self.items]
        title_line = self.title + "\n"
        if len(items) and items[0].text.startswith(title_line):
            # In module-style docstring tagging, the first line of the docstring is the section title.
            # since that is tagged and shown as a title, it is redundant here is the section body.
            # Or that is the intent. This code is a bit hacky.
            items[0].text = items[0].text[len(title_line) :]

        text = "\n".join(item.html() for item in items)
        if text == "":
            # HACK ALERT if text is "" we may have missed some test markup.
            return mark_safe(escape_html(self.rawdoc))
        return mark_safe(text)


class DjangoDocChapter(DocChapter, DjangoDocElement):
    """An object for a Django Documentation Chapter.
    A Chapter is part of a Part and contains Sections.
    """

    @property
    def guide_or_symbol_sections(self):
        if self.guide_sections:
            return self.guide_sections
        return self.sections

    def get_collection(self):
        """Return a list of chapters in the part of this chapter."""
        return self.part.chapters

    def get_uri(self) -> str:
        """Return the URI of this chapter."""
        return f"/{self.part.slug}/{self.slug}/"


class DjangoDocPart(DocPart, DjangoDocElement):
    def __init__(self, doc, title, is_reference=False):
        super(DjangoDocPart, self).__init__(doc, title, is_reference)
        self.chapter_class = DjangoDocChapter

    def get_collection(self):
        """Return a list of parts in this doc"""
        return self.documentation.parts

    def html(self):
        if len(self.tests) == 0:
            return "\n"
        return '<ul class="tests">%s</ul>' % (
            "\n".join(
                "<li>%s</li>" % test.html() for test in self.tests if not test.private
            )
        )

    def get_uri(self) -> str:
        """Return the URI of this part."""
        return f"/{self.slug}/"


class DjangoDocSection(DocSection, DjangoDocElement):
    """An object for a Django Documented Section.
    A Section is part of a Chapter. It can contain subsections.
    """

    def __str__(self):
        return f"== {self.title} ==\n{self.doc}"

    def get_collection(self):
        """Return a list of subsections for this section that this section belongs
        to."""
        return self.chapter.all_sections

    def html_data(self):
        indices = set()
        for test in self.doc.items:
            indices.update(test.test_indices())
        result = {}
        for index in indices:
            result[index] = doc_data.get(
                (self.chapter.part.title, self.chapter.title, self.title, index)
            )
        return result

    def get_uri(self) -> str:
        """Return the URI of this section."""
        return f"/{self.chapter.part.slug}/{self.chapter.slug}/{self.slug}/"


class DjangoDocGuideSection(DjangoDocSection, DjangoDocElement):
    """An object for a Django Documented Guide Section.
    A Guide Section is part of a Chapter. "Colors" or "Special Functions"
    are examples of Guide Sections, and each contains a number of Sections.
    like NamedColors or Orthogonal Polynomials.
    """

    def __init__(
        self,
        chapter: DocChapter,
        title: str,
        text: str,
        submodule,
        installed: bool = True,
    ):
        super().__init__(chapter, title, text, None, installed, False)
        self.section = submodule

    def get_uri(self) -> str:
        """Return the URI of this section."""
        return f"/{self.chapter.part.slug}/{self.chapter.slug}/{self.slug}"


class DjangoDocSubsection(DocSubsection, DjangoDocElement):
    """An object for a Django Documented Subsection.
    A Subsection is part of a Section.
    """

    def __str__(self):
        return f"=== {self.title} ===\n{self.doc}"

    def get_collection(self) -> str:
        """Return a list of subsections of the section."""
        return self.section.subsections

    def html_data(self):
        indices = set()
        for test in self.doc.items:
            indices.update(test.test_indices())
        result = {}
        for index in indices:
            result[index] = doc_data.get(
                (self.chapter.part.title, self.chapter.title, self.title, index)
            )
        return result

    def get_uri(self) -> str:
        """Return the URI of this subsection."""
        return (
            f"/{self.chapter.part.slug}/{self.chapter.slug}/{self.section.slug}/"
            f"{self.slug}/"
        )


class DjangoDocTest(DocTest):
    """
    See DocTest for formatting rules.
    """

    def html(self) -> str:
        result = '<div class="test"><span class="move"></span>'
        result += f'<ul class="test" id="test_{self.index}">'

        result += f'<li class="test">{escape_html(self.test, True)}</li>'

        if self.key is None:
            result += "</ul>"
            result += "</div>"
            return result

        output_for_key = doc_data.get(self.key, None)
        # HACK ALERT:
        # output_for_key is not None, then the output appears
        # mysteriously some other way.
        # But if it is None then test number don't line up and that is a different
        # bug that we address here.
        if output_for_key is None:
            output_for_key = get_results_by_test(self.test, self.key, doc_data)
            results = output_for_key.get("results", [])
            result += '<ul class="out">'
            for r in results:
                for out in r["out"]:
                    result += f'<li class="out">{escape_html(out["text"])}</li>'
                if r["result"]:  # is not None and result['result'].strip():
                    result += f'<li class="result">{r["result"]}</li>'
            result += "</ul>"

        result += "</ul>"
        result += "</div>"
        return result


class DjangoDocTests(DocTests):
    def html(self):
        if len(self.tests) == 0:
            return "\n"
        return '<ul class="tests">%s</ul>' % (
            "\n".join(
                "<li>%s</li>" % test.html() for test in self.tests if not test.private
            )
        )


class DjangoDocText(DocText):
    def html(self) -> str:
        result = escape_html(self.text)
        return result
