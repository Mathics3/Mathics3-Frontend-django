#!/usr/bin/env python
# -*- coding: utf-8 -*-
# FIXME: combine with same thing in Mathics core
"""
Does 2 things which can either be done independently or
as a pipeline:

1. Extracts tests and runs them from static mdoc files and docstrings from
   Mathics built-in functions
2. Creates/updates internal documentation data
"""

import pickle
import sys
from argparse import ArgumentParser
from datetime import datetime
from typing import Literal

import mathics
from mathics import version_string
from mathics.core.load_builtin import import_and_load_builtins
from mathics.doc.doc_entries import Tests
from mathics.doc.utils import load_doctest_data, open_ensure_dir
from mathics.docpipeline import DocTestPipeline, test_all, test_chapters, test_sections
from mathics.timing import show_lru_cache_statistics

from mathics_django.settings import get_doctest_html_data_path

MAX_TESTS: Literal = 100000  # A number greater than the total number of tests.


def build_arg_parser():
    """Build the argument parser"""
    parser = ArgumentParser(description="Mathics3 test suite.", add_help=False)
    parser.add_argument(
        "--help", "-h", help="show this help message and exit", action="help"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s " + mathics.__version__,
    )
    parser.add_argument(
        "--chapters",
        "-c",
        dest="chapters",
        metavar="CHAPTER",
        help="only test CHAPTER(s). "
        "You can list multiple chapters by adding a comma (and no space) in between chapter names.",
    )
    parser.add_argument(
        "--sections",
        "-s",
        dest="sections",
        metavar="SECTION",
        help="only test SECTION(s). "
        "You can list multiple sections by adding a comma (and no space) in between section names.",
    )
    parser.add_argument(
        "--exclude",
        "-X",
        default="",
        dest="exclude",
        metavar="SECTION",
        help="exclude SECTION(s). "
        "You can list multiple sections by adding a comma (and no space) in between section names.",
    )
    parser.add_argument(
        "--logfile",
        "-f",
        dest="logfilename",
        metavar="LOGFILENAME",
        help="stores the output in [logfilename]. ",
    )
    parser.add_argument(
        "--load-module",
        "-l",
        dest="pymathics",
        metavar="MATHIC3-MODULES",
        help="load Mathics3 module MATHICS3-MODULES. "
        "You can list multiple Mathics3 Modules by adding a comma (and no space) in between "
        "module names.",
    )
    parser.add_argument(
        "--time-each",
        "-d",
        dest="elapsed_times",
        action="store_true",
        help="check the time that take each test to parse, evaluate and compare.",
    )

    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        action="store_true",
        help="generate pickled internal document data",
    )
    parser.add_argument(
        "--doc-only",
        dest="doc_only",
        action="store_true",
        help=(
            "generate pickled internal document data without running tests; "
            "Can't be used with --section or --reload."
        ),
    )
    parser.add_argument(
        "--reload",
        "-r",
        dest="reload",
        action="store_true",
        help="reload pickled internal document data, before possibly adding to it",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        dest="quiet",
        action="store_true",
        help="hide passed tests",
    )
    parser.add_argument(
        "--keep-going",
        "-k",
        dest="keep_going",
        action="store_true",
        help="create documentation even if there is a test failure",
    )
    parser.add_argument(
        "--stop-on-failure",
        "-x",
        dest="stop_on_failure",
        action="store_true",
        help="stop on failure",
    )
    parser.add_argument(
        "--skip",
        metavar="N",
        dest="skip",
        type=int,
        default=0,
        help="skip the first N tests",
    )
    parser.add_argument(
        "--count",
        metavar="N",
        dest="count",
        type=int,
        default=MAX_TESTS,
        help="run only  N tests",
    )
    parser.add_argument(
        "--show-statistics",
        action="store_true",
        help="print cache statistics",
    )
    return parser.parse_args()


def create_output(test_pipeline, tests):
    """
    Populate ``doctest_data`` with the results of the
    ``tests`` in the format ``output_format``
    """
    output_format = test_pipeline.parameters.output_format
    if test_pipeline.session.definitions is None:
        test_pipeline.print_and_log("Definitions are not initialized.")
        return

    doctest_data = test_pipeline.output_data
    test_pipeline.reset_user_definitions()
    session = test_pipeline.session

    # By default, latex and xml form produce outputs in `TraditionalForm`.
    # For the documentation, we want StandardForm.
    if output_format in ("latex", "xml"):

        def out_wrapper(expr):
            return f"StandardForm[{expr}]"

    else:

        def out_wrapper(expr):
            return expr

    if isinstance(tests, Tests):
        for test in tests.tests:
            key = test.key
            try:
                result = session.evaluate_as_in_cli(
                    out_wrapper(test), form=output_format
                )
            except Exception:  # noqa
                result = None
            if result is None:
                result_data = []
            else:
                result_data = result.get_data()
                result_data["form"] = output_format
            result = [result_data]

            doctest_data[key] = {
                "query": test.test,
                "results": result,
            }

    else:
        for test in tests:
            if test.private:
                continue
            key = test.key
            try:
                result = session.evaluate_as_in_cli(
                    out_wrapper(test.test), form=output_format
                )
            except Exception:  # noqa
                result = None
            if result is None:
                result_data = []
            else:
                result_data = result.get_data()
                result_data["form"] = output_format
            result = [result_data]

            doctest_data[key] = {
                "query": test.test,
                "results": result,
            }


def save_doctest_data(output_data):
    """
    Save doctest tests and test results to a Python PCL file.

    ``output_data`` is a dictionary of test results. The key is a tuple
    of:
    * Part name,
    * Chapter name,
    * [Guide Section name],
    * Section name,
    * Subsection name,
    * test number
    and the value is a dictionary of a Result.getdata() dictionary.
    """
    doctest_html_data_path = get_doctest_html_data_path(
        should_be_readable=False, create_parent=True
    )
    print(f"Writing internal document data to {doctest_html_data_path}")
    with open_ensure_dir(doctest_html_data_path, "wb") as output_file:
        pickle.dump(output_data, output_file, 4)


def write_doctest_data(doctest_pipeline: DocTestPipeline, output_format=None):
    """
    Get doctest information, which involves running the tests to obtain
    test results and write out both the tests and the test results.
    """
    test_parameters = doctest_pipeline.parameters
    if not test_parameters.quiet:
        doctest_pipeline.print_and_log(
            f"Extracting internal doc data for {version_string}"
        )
        print("This may take a while...")

    try:
        doctest_pipeline.output_data = (
            load_doctest_data(test_parameters.data_path)
            if test_parameters.reload
            else {}
        )
        for tests in doctest_pipeline.documentation.get_tests():
            create_output(
                doctest_pipeline,
                tests,
            )
    except KeyboardInterrupt:
        doctest_pipeline.print_and_log("\nAborted.\n")
        return

    print("done.\n")

    save_doctest_data(doctest_pipeline)


def main():
    args = build_arg_parser()
    data_path = (
        get_doctest_html_data_path(should_be_readable=False, create_parent=True)
        if args.output
        else None
    )
    test_pipeline = DocTestPipeline(args, output_format="xml", data_path=data_path)
    test_status = test_pipeline.status

    if args.sections:
        include_sections = set(args.sections.split(","))
        exclude_subsections = set(args.exclude.split(","))
        start_time = datetime.now()
        test_sections(test_pipeline, include_sections, exclude_subsections)
    elif args.chapters:
        start_time = datetime.now()
        include_chapters = set(args.chapters.split(","))
        exclude_sections = set(args.exclude.split(","))
        test_chapters(test_pipeline, include_chapters, exclude_sections)
    else:
        if args.doc_only:
            write_doctest_data(test_pipeline)
        else:
            excludes = set(args.exclude.split(","))
            start_time = datetime.now()
            test_all(test_pipeline, excludes=excludes)

    if test_status.total > 0 and start_time is not None:
        print("Test evaluation took ", datetime.now() - start_time)

    if test_pipeline.logfile:
        test_pipeline.logfile.close()
    if args.show_statistics:
        show_lru_cache_statistics()

    if test_status.failed == 0:
        print("\nOK")
    else:
        print("\nFAILED")
        sys.exit(1)  # Travis-CI knows the tests have failed


if __name__ == "__main__":
    import_and_load_builtins()
    main()
