from . import models

# Only import tests when running in test mode
def post_init_hook(env):
    # Tests will be imported when run through test command
    pass