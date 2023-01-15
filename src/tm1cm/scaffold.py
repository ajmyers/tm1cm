import logging
import os
import shutil
import zipfile

FOLDER_STRUCTURE = [
    'config',
    'config/default',
    'config/test',
    'config/prod',
    'data',
]


def create_scaffold(path):
    """Entry point for create-app.

    Args:
        path (str): Path of the project

    Raises:
        ValueError: Raised if path already exists
    """
    logger = logging.getLogger(__name__)

    logger.debug('create_scaffold called with path: {}'.format(path))
    if os.path.exists(path):
        raise ValueError('path: {} already exists'.format(path))

    try:
        for folder in FOLDER_STRUCTURE:
            new_path = os.path.join(path, folder)
            logger.debug('creating: {}'.format(new_path))
            os.makedirs(new_path)
    except Exception:
        raise

    try:
        logger.debug(__file__)
        include_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'include')

        if '.sublime-package' in include_path:
            pkg_path, pkg_suffix = include_path.split('.sublime-package' + os.sep)
            pkg_path = pkg_path + '.sublime-package'

            with zipfile.PyZipFile(pkg_path, mode="r") as zip_pkg:
                fn = '.gitignore'
                with zip_pkg.open(os.path.join(pkg_suffix, fn)) as zip_file:
                    content = zip_file.read()
                with open(os.path.join(path, fn), 'wb') as fp:
                    fp.write(content)

                for f in ['connect.yaml', 'tm1cm.yaml', 'credentials.yaml']:
                    with zip_pkg.open(os.path.join(pkg_suffix, f)) as zip_file:
                        content = zip_file.read()
                    with open(os.path.join(path, 'config', 'default', f), 'wb') as fp:
                        fp.write(content)

                    if f == 'connect.yaml':
                        with open(os.path.join(path, 'config', 'test', f), 'wb') as fp:
                            fp.write(content)

                        with open(os.path.join(path, 'config', 'prod', f), 'wb') as fp:
                            fp.write(content)

            return

        copy_from = os.path.join(include_path, '.gitignore')
        copy_to = os.path.join(path, '.gitignore')
        logger.debug('copying: {} to {}'.format(copy_from, copy_to))
        shutil.copy(copy_from, copy_to)

        for f in ['connect.yaml', 'tm1cm.yaml', 'credentials.yaml']:
            copy_from = os.path.join(include_path, f)
            copy_to = os.path.join(path, 'config', 'default', f)
            logger.debug('copying: {} to {}'.format(copy_from, copy_to))
            shutil.copy(copy_from, copy_to)

            if f == 'connect.yaml':
                copy_to = os.path.join(path, 'config', 'test', f)
                shutil.copy(copy_from, copy_to)

                copy_to = os.path.join(path, 'config', 'prod', f)
                shutil.copy(copy_from, copy_to)

    except Exception:
        raise

    logger.info('created new scaffold at {}'.format(path))
