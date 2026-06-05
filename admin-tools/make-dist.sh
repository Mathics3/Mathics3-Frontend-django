#!/bin/bash
PACKAGE=Mathics3-Frontend-django

# FIXME put some of the below in a common routine
function finish {
	cd $mathics3_django_owd
}

cd $(dirname ${BASH_SOURCE[0]})
mathics3_django_owd=$(pwd)
trap finish EXIT

if ! source ./pyenv-versions ; then
	exit $?
fi


cd ..
source mathics_django/version.py
echo $__version__

cp -v ${HOME}/.local/var/Mathics3/doc_html_data.pcl mathics_django/doc/
pyversion=3.14
if ! pyenv local $pyversion ; then
    exit $?
fi
rm -fr build
python -m build --wheel
python -m build --sdist
finish
