import logging
import os
import shutil

FOLDER_STRUCTURE = [
    'config',
    'config/default',
    'config/test',
    'config/staging',
    'config/prod',
    'data',
    'data/cube',
    'data/dimension',
    'data/hierarchy',
    'data/process',
    'data/rule',
    'data/view',
    'data/view_data',
    'data/subset',
    'scripts',
    'scripts/local',
    'scripts/shared',
    'files',
    'files/local',
    'files/shared',
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
        logger.debug(include_path)
        for f in ['connect.yaml', 'tm1cm.yaml', 'credentials.yaml']:
            copy_from = os.path.join(include_path, f)
            copy_to = os.path.join(path, 'config/default', f)
            logger.debug('copying: {} to {}'.format(copy_from, copy_to))
            shutil.copy(copy_from, copy_to)

        copy_from = os.path.join(include_path, '.gitignore')
        copy_to = os.path.join(path, '.gitignore')
        logger.debug('copying: {} to {}'.format(copy_from, copy_to))
        shutil.copy(copy_from, copy_to)
    except Exception:
        raise

    logger.info('created new scaffold at {}'.format(path))
