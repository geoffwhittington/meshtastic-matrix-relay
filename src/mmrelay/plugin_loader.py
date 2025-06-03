# -- at line 59 ------------------------------------------------------------
def clone_or_update_repo(repo_url, ref, plugins_dir):
    """Clone or update a Git repository for community plugins.
    
    Args:
        repo_url (str): Git repository URL to clone/update
        ref (dict): Reference specification with keys:
                   - type: "tag" or "branch" 
                   - value: tag name or branch name
        plugins_dir (str): Directory where the repository should be cloned
        
    Returns:
        bool: True if successful, False if clone/update failed
        
    Handles complex Git operations including:
    - Cloning new repositories with specific tags/branches
    - Updating existing repositories and switching refs
    - Installing requirements.txt dependencies via pip or pipx
    - Fallback to default branches (main/master) when specified ref fails
    - Robust error handling and logging
    
    The function automatically installs Python dependencies if a requirements.txt
    file is found in the repository root.
    """
    # Extract the repository name from the URL
    repo_name = os.path.splitext(os.path.basename(repo_url.rstrip("/")))[0]
    repo_path = os.path.join(plugins_dir, repo_name)
    ...

# -- at line 499 -----------------------------------------------------------
def load_plugins_from_directory(directory, recursive=False):
    """Load plugin classes from Python files in a directory.
    
    Args:
        directory (str): Directory path to search for plugin files
        recursive (bool): Whether to search subdirectories recursively
        
    Returns:
        list: List of instantiated plugin objects found in the directory
        
    Scans for .py files and attempts to import each as a module. Looks for
    a 'Plugin' class in each module and instantiates it if found.
    
    Features:
    - Automatic dependency installation for missing imports (via pip/pipx)
    - Compatibility layer for import paths (plugins vs mmrelay.plugins)
    - Proper sys.path management for plugin directory imports
    - Comprehensive error handling and logging
    
    Skips files that don't define a Plugin class or have import errors
    that can't be automatically resolved.
    """
    plugins = []
    if os.path.isdir(directory):
        ...

# -- at line 619 -----------------------------------------------------------
def load_plugins(passed_config=None):
    """Load and initialize all active plugins based on configuration.
    
    Args:
        passed_config (dict, optional): Configuration dictionary to use.
                                       If None, uses global config variable.
        
    Returns:
        list: List of active plugin instances sorted by priority
        
    This is the main plugin loading function that:
    - Loads core plugins from mmrelay.plugins package
    - Processes custom plugins from ~/.mmrelay/plugins/custom and plugins/custom
    - Downloads and loads community plugins from configured Git repositories
    - Filters plugins based on active status in configuration
    - Sorts active plugins by priority and calls their start() method
    - Sets up proper plugin configuration and channel mapping
    
    Only plugins explicitly marked as active=true in config are loaded.
    Custom and community plugins are cloned/updated automatically.
    """
    global sorted_active_plugins
    global plugins_loaded
    global config
    ...