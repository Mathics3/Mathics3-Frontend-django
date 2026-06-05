# A GNU Makefile to run various tasks - compatibility for us old-timers.

# Note: This makefile include remake-style target comments.
# These comments before the targets start with #:
# remake --tasks to shows the targets and the comments

GIT2CL ?= admin-tools/git2cl
MATHICS_CHARACTER_ENCODING ?= ASCII
DAPHNE ?= daphne
PYTHON ?= python
PIP ?= pip3
RM  ?= rm

# Set default value for port
o   ?= --port 8000

MATHICS3_MODULE_OPTION ?= --load-module pymathics.graph,pymathics.natlang

.PHONY: all build \
	ChangeLog-without-corrections \
	check clean \
	develop \
        dist \
        doc \
        doctest-html-data \
        djangotest \
        docker \
	gstest pytest \
	rmChangeLog \
	runserver \
	runserver-debug \
	runserver-production \
	test

THREEJS=mathics_django/web/media/js/mathics-threejs-backend/index.js mathics_django/web/media/js/mathics-threejs-backend/version.json
MATHICS3_SANDBOX	?=
ifeq ($(OS),Windows_NT)
	MATHICS3_SANDBOX = t
else
	UNAME_S := $(shell uname -s)
	ifeq ($(UNAME_S),Darwin)
		MATHICS3_SANDBOX = t
	endif
endif

#: Default target - same as "develop".
all: develop

#: Build everything needed to install.
build: $(THREEJS)
	$(PYTHON) ./setup.py build

check: djangotest doctest-workaround

#: Remove derived files.
clean:
	@rm $(THREEJS) || true;

#: Set up to run from the source tree.
develop: $(THREEJS)
	$(PIP) install -e .

#: Make distribution: wheels, eggs, tarball.
dist: $(THREEJS)
	./admin-tools/make-dist.sh

#: Run Django tests.
djangotest: $(THREEJS)
	cd mathics_django && $(PYTHON) manage.py test test_django

#: Run tests that appear in docstring in the code.
doctest-workaround:
	MATHICS_CHARACTER_ENCODING=$(MATHICS_CHARACTER_ENCODING) MATHICS3_SANDBOX=$(MATHICS3_SANDBOX) $(PYTHON) mathics_django/docpipeline.py --exclude=NIntegrate,MaxRecursion,PythonCProfileEvaluation
	MATHICS_CHARACTER_ENCODING=$(MATHICS_CHARACTER_ENCODING) MATHICS3_SANDBOX=$(MATHICS3_SANDBOX) $(PYTHON) mathics_django/docpipeline.py --sections=NIntegrate,MaxRecursion,

#: Run tests that appear in docstring in the code.
doctest: $(THREEJS)
	MATHICS_CHARACTER_ENCODING=$(MATHICS_CHARACTER_ENCODING) MATHICS3_SANDBOX=$(MATHICS3_SANDBOX) $(PYTHON) mathics_django/docpipeline.py $o

#: Create doctest test data and test results that is used in online documentation
doctest-html-data:
	MATHICS_CHARACTER_ENCODING="UTF-8"  $(PYTHON) mathics_django/docpipeline.py --output --keep-going $(MATHICS3_MODULE_OPTION)

#: Create doctest test data in HTML format including all Mathics3 Modules
doctest-html-data-full:
	MATHICS_CHARACTER_ENCODING="UTF-8"  $(PYTHON) mathics_django/docpipeline.py --output --keep-going $(MATHICS3_MODULE_OPTION)
#: Install Mathics-Django
install: $(THREEJS)
	$(PYTHON) setup.py install

#: Run Django-based server in production mode.
runserver-production: $(THREEJS)
	MATHICS3_DJANGO_DEBUG=false $(DAPHNE) -b 0.0.0.0 -p 8000 mathics_django.asgi:application

#: Run Django-based server in development mode. Use environment variable "o" for manage options
runserver: $(THREEJS)
	MATHICS3_DJANGO_DISPLAY_EXCEPTIONS=true MATHICS3_DJANGO_LOG_ON_CONSOLE=false $(PYTHON) mathics_django/manage.py runserver $o

#: Run Django-based server in development mode with debug. Use environment variable "o" for manage options
runserver-debug: $(THREEJS)
	MATHICS3_DJANGO_DEBUG=true MATHICS3_DJANGO_DISPLAY_EXCEPTIONS=true MATHICS3_DJANGO_LOG_ON_CONSOLE=true $(PYTHON) mathics_django/manage.py runserver $o

#: Run Django-based server in testserver mode. Use environment variable "o" for manage options
testserver: $(THREEJS)
	$(PYTHON) mathics_django/manage.py testserver $o

node_modules/\@mathicsorg/mathics-threejs-backend/package.json node_modules/@mathicsorg/mathics-threejs-backend/package.json:
	npm install @mathicsorg/mathics-threejs-backend --loglevel=error

#: Install mathics-threejs-backend with npm and copy the necessary files to the right place.
build_mathics-threejs-backend: node_modules/\@mathicsorg/mathics-threejs-backend/package.json
	cp node_modules/\@mathicsorg/mathics-threejs-backend/docs/build.js mathics_django/web/media/js/mathics-threejs-backend/index.js; \
	cp node_modules/\@mathicsorg/mathics-threejs-backend/package.json mathics_django/web/media/js/mathics-threejs-backend/version.json


$(THREEJS): node_modules/@mathicsorg/mathics-threejs-backend/package.json package.json
	$(MAKE) build_mathics-threejs-backend

#: Create ChangeLog from version control without corrections
ChangeLog-without-corrections:
	git log --pretty --numstat --summary | $(GIT2CL) >ChangeLog

#: Remove ChangeLog
rmChangeLog:
	$(RM) ChangeLog || true

#: Create a ChangeLog from git via git log and git2cl
ChangeLog: rmChangeLog ChangeLog-without-corrections
	patch -p0 ChangeLog < ChangeLog-spell-corrected.diff
