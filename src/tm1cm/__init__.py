import os

# Without git, GitPython refuses to be imported at all, and tm1cm with it: let it import, and fail
# when git is first used, where tm1cm.errors can say that git is missing
os.environ.setdefault('GIT_PYTHON_REFRESH', 'quiet')
