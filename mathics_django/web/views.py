# -*- coding: utf-8 -*-

import traceback

from django.core.handlers.wsgi import WSGIRequest
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.template import loader
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonTracebackLexer

try:
    import ujson as json
except ImportError:
    import json

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import User
from django.core.mail import send_mail
from mathics.core.definitions import Definitions
from mathics.core.evaluation import Message, Result
from mathics.settings import TIMEOUT, default_pymathics_modules

from mathics_django.web.html_forms import LoginForm, SaveForm
from mathics_django.web.models import Query, Worksheet, get_session_evaluation

html_formatter = HtmlFormatter(noclasses=True)

if settings.DEBUG:
    JSON_CONTENT_TYPE = "text/html"
else:
    JSON_CONTENT_TYPE = "application/json"


class JsonResponse(HttpResponse):
    def __init__(self, result={}):
        response = json.dumps(result)
        super(JsonResponse, self).__init__(
            response.encode("UTF-8"), content_type=JSON_CONTENT_TYPE
        )


def delete(request):
    user = request.user
    if settings.REQUIRE_LOGIN and not is_authenticated(user):
        raise Http404
    name = request.POST.get("name", "")
    try:
        if is_authenticated(user):
            deleted = user.worksheets.get(name=name).delete()
        else:
            deleted = Worksheet.objects.get(user__isnull=True, name=name).delete()
        content = str(deleted[0])
    except Worksheet.DoesNotExist:
        content = ""

    return JsonResponse(
        {
            "content": content,
        }
    )


def email_user(user, subject, text):
    send_mail(
        subject, text, "noreply@mathics.net", [user.username], fail_silently=False
    )


def error_404_view(request: WSGIRequest, exception):
    t = loader.get_template("404.html")
    return HttpResponseNotFound(t.render({"request_path": request.path}))


def error_500_view(request: WSGIRequest):
    t = loader.get_template("500.html")
    return HttpResponseServerError(t.render({"request_path": request.path}))


def get_worksheets(request):
    if settings.REQUIRE_LOGIN and not is_authenticated(request.user):
        result = []
    else:
        if is_authenticated(request.user):
            result = list(request.user.worksheets.order_by("name").values("name"))
        else:
            result = list(
                Worksheet.objects.filter(user__isnull=True)
                .order_by("name")
                .values("name")
            )
    return JsonResponse(
        {
            "worksheets": result,
        }
    )


def is_authenticated(user) -> bool:
    if callable(user.is_authenticated):
        return user.is_authenticated()
    return user.is_authenticated


def login(request: WSGIRequest) -> JsonResponse:
    if settings.DEBUG and not request.POST:
        request.POST = request.GET
    form = LoginForm(request.POST)
    result = ""
    general_errors = []
    if form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        if password:
            user = auth.authenticate(username=email, password=password)
            if user is None:
                general_errors = ["Invalid username and/or password."]
            else:
                result = "ok"
                auth.login(request, user)
        else:
            password = nicepass()
            try:
                user = User.objects.get(username=email)
                result = "reset"
                email_user(
                    user,
                    "Your password at mathics.net",
                    (
                        """You have reset your password at mathics.net.\n
Your password is: %s\n\nYours,\nThe Mathics3 team"""
                    )
                    % password,
                )
            except User.DoesNotExist:
                user = User(username=email, email=email)
                result = "created"
                email_user(
                    user,
                    "New account at mathics.net",
                    """Welcome to mathics.net!\n
Your password is: %s\n\nYours,\nThe Mathics3 team"""
                    % password,
                )
            user.set_password(password)
            user.save()

    return JsonResponse(
        {
            "result": result,
            "form": form.as_json(general_errors=general_errors),
        }
    )


def logout(request: WSGIRequest) -> JsonResponse:
    auth.logout(request)
    return JsonResponse()


def main_view(request: WSGIRequest):
    """
    This is what people normally see when running the server.
    It contains the banner line with logo and icons to load and save and
    a worksheet area to evaluate expressions. Off the the right is optional documentation.
    """
    context = {
        "login_form": LoginForm(),
        "save_form": SaveForm(),
        "require_login": settings.REQUIRE_LOGIN,
    }
    return render(request, "main.html", context)


# nicepass is taken from http://code.activestate.com/recipes/410076/
def nicepass(alpha=6, numeric=2):
    """
    returns a human-readble password (say rol86din instead of
    a difficult to remember K8Yn9muL )
    """
    import random
    import string

    vowels = ["a", "e", "i", "o", "u"]
    consonants = [a for a in string.ascii_lowercase if a not in vowels]
    digits = string.digits

    # utility functions
    def a_part(slen):
        ret = ""
        for i in range(slen):
            if i % 2 == 0:
                randid = random.randint(0, 20)  # number of consonants
                ret += consonants[randid]
            else:
                randid = random.randint(0, 4)  # number of vowels
                ret += vowels[randid]
        return ret

    def n_part(slen):
        ret = ""
        for i in range(slen):
            randid = random.randint(0, 9)  # number of digits
            ret += digits[randid]
        return ret

    fpl = alpha / 2
    if alpha % 2:
        fpl = int(alpha / 2) + 1
    lpl = alpha - fpl

    start = a_part(fpl)
    mid = n_part(numeric)
    end = a_part(lpl)

    return "%s%s%s" % (start, mid, end)


def open(request: WSGIRequest):
    user = request.user
    if settings.REQUIRE_LOGIN and not is_authenticated(user):
        raise Http404
    name = request.POST.get("name", "")
    try:
        if is_authenticated(user):
            worksheet = user.worksheets.get(name=name)
        else:
            worksheet = Worksheet.objects.get(user__isnull=True, name=name)
        content = worksheet.content
    except Worksheet.DoesNotExist:
        content = ""

    return JsonResponse(
        {
            "content": content,
        }
    )


def query(request: WSGIRequest) -> JsonResponse:
    """
    Handles Mathics3 input expressions.
    """
    global definitions
    from mathics.core.parser import MathicsMultiLineFeeder

    input = request.POST.get("query", "")
    if settings.DEBUG and not input:
        input = request.GET.get("query", "")

    if settings.LOG_QUERIES:
        query_log = Query(
            query=input,
            error=True,
            browser=request.META.get("HTTP_USER_AGENT", ""),
            remote_user=request.META.get("REMOTE_USER", ""),
            remote_addr=request.META.get("REMOTE_ADDR", ""),
            remote_host=request.META.get("REMOTE_HOST", ""),
            meta=str(request.META),
            log="",
        )
        query_log.save()

    evaluation = get_session_evaluation(request.session)
    feeder = MathicsMultiLineFeeder(input, "Django-cell-input")
    results = []
    try:
        while not feeder.empty():
            (
                expr,
                source_code,
                messages,
            ) = evaluation.parse_feeder_returning_code_and_messages(feeder)
            if len(messages) > 0 and messages[0].tag in ("sntxf", "sntxb", "sntxi"):
                # Syntax or Parse errors.

                # For simplicity, when there is an error there will be just one
                # error shown and we will use a dictionary for that rather than
                # an array of dictionaries. This simplifies Javascript, formatting
                # because at the top level we don't need a list element.

                # Strip quotes from messages.
                message = evaluation.out[0]

                if message.text.startswith('"') and message.text.endswith('"'):
                    message.text = message.text[1:-1]
                results.append(
                    Result(
                        out=evaluation.out,
                        result=None,
                        line_no=None,
                        last_eval=None,
                        form="Syntax Error",
                    )
                )

                if settings.LOG_ON_CONSOLE:
                    print(source_code)
                    print(message.text)

                evaluation.out = []
                expr = None

            if expr is None:
                # comment or an error.
                # TODO: source_code should have '(* ... *)' and
                # better would be to create tagged result.
                continue

            result = evaluation.evaluate(expr, timeout=TIMEOUT)
            results.append(result)

    except SystemExit:
        results = []
        result = None
        definitions = Definitions(
            add_builtin=True, extension_modules=default_pymathics_modules
        )
        evaluation.definitions = definitions

    except Exception as exc:

        def html_format_traceback_line(tb_line: str) -> str:
            tb = highlight(tb_line, PythonTracebackLexer(), html_formatter)
            return f'<p style="white-space: pre-wrap; word-wrap: break-word;">{tb}</p>'

        # Should we show the Python exception details back to the user?
        if settings.DEBUG and settings.DISPLAY_EXCEPTIONS:
            call_stack = traceback.format_exception(exc)
            # TODO: we may want to do other processing on the traceback
            #       like splitting up lines. Encapsulate the below and put
            #       in a function.
            # FIXME: allow the the stack limit to be user settable

            html_formatted_callstack = []
            if len(call_stack) > 18:
                html_formatted_callstack = [html_format_traceback_line(call_stack[0])]
                html_formatted_callstack += [
                    html_format_traceback_line(tb_line) for tb_line in call_stack[1:9]
                ]
                html_formatted_callstack.append("<p>...</p>")
                html_formatted_callstack += [
                    html_format_traceback_line(tb_line) for tb_line in call_stack[-9:]
                ]
            else:
                html_formatted_callstack = [
                    html_format_traceback_line(tb_line) for tb_line in call_stack
                ]

            except_head = f"Exception raised: {exc}"
            message = Message(
                "Python Exception",
                tag="exception",
                text=[except_head] + html_formatted_callstack,
            )
            results.append(
                Result(
                    out=[message],
                    result=None,
                    line_no=None,
                    last_eval=None,
                    form="Python Exception",
                )
            )
        else:
            raise
    result = {
        "results": [result.get_data() for result in results],
    }
    if settings.LOG_ON_CONSOLE:
        from pprint import pprint as pp

        print(evaluation.timeout)
        pp(result)
        # query_log.timeout = evaluation.timeout
        # query_log.result = str(result)  # evaluation.results
        # query_log.error = False
        # query_log.save()
    return JsonResponse(result)


def require_ajax_login(f):
    return f


@require_ajax_login
def save(request: WSGIRequest):
    if settings.DEBUG and not request.POST:
        request.POST = request.GET
    if settings.REQUIRE_LOGIN and not is_authenticated(request.user):
        raise Http404
    form = SaveForm(request.POST)
    overwrite = request.POST.get("overwrite", False)
    result = ""
    if form.is_valid():
        content = request.POST.get("content", "")
        name = form.cleaned_data["name"]
        user = request.user
        if not is_authenticated(user):
            user = None
        try:
            worksheet = Worksheet.objects.get(user=user, name=name)
            if overwrite:
                worksheet.content = content
            else:
                result = "overwrite"
        except Worksheet.DoesNotExist:
            worksheet = Worksheet(user=user, name=name, content=content)
        worksheet.save()

    return JsonResponse(
        {
            "form": form.as_json(),
            "result": result,
        }
    )
