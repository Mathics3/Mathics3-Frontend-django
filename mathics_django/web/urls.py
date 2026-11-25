# -*- coding: utf-8 -*-
"""This module handles the mapping of URI's to
the functions that get called.

All of the callback functions are located in mathics_django.web.views.
"""

from django.urls import re_path

from mathics_django.web.controllers.about import about_page
from mathics_django.web.controllers.doc import (
    doc,
    doc_chapter,
    doc_part,
    doc_search,
    doc_section,
    doc_subsection,
)

# These are the callback functions.
from mathics_django.web.views import (
    completions,
    delete,
    get_worksheets,
    login,
    logout,
    main_view,
    open,
    query,
    save,
)

# These patterns map URI's a function to call to generate HTML output.
# Note that although what we have here are URIs not URLs.
urlpatterns = [
    # 'mathics.web.views',
    re_path(r"^$", main_view),
    re_path(r"^about(?:\.htm(?:l)?)?$", about_page),
    re_path(r"^ajax/query/$", query),
    re_path(r"^ajax/completions/$", completions),
    re_path(r"^ajax/login/$", login),
    re_path(r"^ajax/logout/$", logout),
    re_path(r"^ajax/save/$", save),
    re_path(r"^ajax/open/$", open),
    re_path(r"^ajax/delete/$", delete),
    re_path(r"^ajax/getworksheets/$", get_worksheets),
    re_path(r"^(?P<ajax>(?:ajax/)?)doc/$", doc),
    re_path(r"^ajax/doc/search/$", doc_search),
    re_path(r"^(?P<ajax>(?:ajax/)?)doc/(?P<part>[\w-]+)/$", doc_part),
    re_path(
        r"^(?P<ajax>(?:ajax/)?)doc/(?P<part>[\w-]+)/(?P<chapter>[\w-]+)/$", doc_chapter
    ),
    re_path(
        r"^(?P<ajax>(?:ajax/)?)doc/(?P<part>[\w-]+)/(?P<chapter>[\w-]+)/"
        r"(?P<section>[$\w-]+)/$",
        doc_section,
    ),
    re_path(
        r"^(?P<ajax>(?:ajax/)?)doc/(?P<part>[\w-]+)/(?P<chapter>[\w-]+)/"
        r"(?P<section>[$\w-]+)/(?P<subsection>[$\w-]+)/$",
        doc_subsection,
    ),
]
