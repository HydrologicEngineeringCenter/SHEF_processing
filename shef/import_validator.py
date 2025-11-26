import importlib
import importlib.abc
import sys
from types import ModuleType
from typing import Dict, Optional, Sequence, Union

expected_loader_globals: Dict[str, Union[type, str]] = {
    "loader_options": str,
    "loader_description": str,
    "loader_version": str,
    "loader_class": "AbstractLoader",
    "can_unload": bool,
}

expected_exporter_globals: Dict[str, Union[type, str]] = {
    "exporter_parameters": str,
    "exporter_description": str,
    "exporter_version": str,
    "exporter_class": "AbstractExporter",
    "loader_class": "AbstractLoader",
}


class LoaderModuleValidatedLoader(importlib.abc.Loader):
    """
    Wraps loader module loaders to enforce modules to have certain global variables
    """

    def __init__(self, loader: importlib.abc.Loader) -> None:
        self.loader = loader

    def create_module(
        self, spec: importlib.machinery.ModuleSpec
    ) -> Optional[ModuleType]:
        if hasattr(self.loader, "create_module"):
            return self.loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        # run original loader
        self.loader.exec_module(module)
        # validate globals
        errors = []
        if not module.__name__.endswith("_loader"):
            errors.append(f"{module.__name__} is not named <loader-name>_loader")
        for varname in sorted(expected_loader_globals):
            if not hasattr(module, varname):
                errors.append(
                    f"{module.__name__} is missing required global variable {varname}"
                )
                continue
            val = getattr(module, varname)
            expected_type: Union[type, str] = expected_loader_globals[varname]
            if isinstance(expected_type, str):
                try:
                    class_hierarchy = list(map(lambda c: c.__name__, val.mro()))
                    okay = expected_type in class_hierarchy
                    if okay and varname == "loader_class":
                        okay = hasattr(module, class_hierarchy[0])
                except:
                    okay = False
                if not okay:
                    errors.append(
                        f"{module.__name__} has incorrect type for global variable {varname}: expected subcalss of {expected_type}, got {type(val)}"
                    )
            else:
                if not isinstance(val, expected_type):
                    errors.append(
                        f"{module.__name__} has incorrect type for global variable {varname}: expected {expected_type}, got {type(val)}"
                    )
        if errors:
            raise ImportError("\n\t" + "\n\t".join(errors))


class ExporterModuleValidatedLoader(importlib.abc.Loader):
    """
    Wraps exporter module loaders to enforce modules to have certain global variables
    """

    def __init__(self, loader: importlib.abc.Loader) -> None:
        self.loader = loader

    def create_module(
        self, spec: importlib.machinery.ModuleSpec
    ) -> Optional[ModuleType]:
        if hasattr(self.loader, "create_module"):
            return self.loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        # run original loader
        self.loader.exec_module(module)
        # validate globals
        errors = []
        if not module.__name__.endswith("_exporter"):
            errors.append(f"{module.__name__} is not named <exporter-name>_exporter")
        for varname in sorted(expected_exporter_globals):
            if not hasattr(module, varname):
                errors.append(
                    f"{module.__name__} is missing required global variable {varname}"
                )
                continue
            val = getattr(module, varname)
            expected_type: Union[type, str] = expected_exporter_globals[varname]
            if isinstance(expected_type, str):
                try:
                    class_hierarchy = list(map(lambda c: c.__name__, val.mro()))
                    okay = expected_type in class_hierarchy
                    if okay and varname == "exporter_class":
                        okay = hasattr(module, class_hierarchy[0])
                except:
                    okay = False
                if not okay:
                    errors.append(
                        f"{module.__name__} has incorrect type for global variable {varname}: expected subcalss of {expected_type}, got {type(val)}"
                    )
            else:
                if not isinstance(val, expected_type):
                    errors.append(
                        f"{module.__name__} has incorrect type for global variable {varname}: expected {expected_type}, got {type(val)}"
                    )
        if errors:
            raise ImportError("\n\t" + "\n\t".join(errors))


class ValidatedFinder(importlib.abc.MetaPathFinder):
    """
    Meta path finder that warps loaders for certain modules
    """

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[ModuleType] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        if fullname.startswith("shef.loaders") or fullname.startswith("shef.exporters"):
            for finder in sys.meta_path:
                if finder is self or not hasattr(finder, "find_spec"):
                    continue

                if fullname.startswith("shef.loaders."):
                    if fullname in "shef.loaders.shared":
                        return None
                    spec = finder.find_spec(fullname, path, target)
                    if spec and spec.loader:
                        spec.loader = LoaderModuleValidatedLoader(spec.loader)
                        return spec
                elif fullname.startswith("shef.exporters."):
                    spec = finder.find_spec(fullname, path, target)
                    if spec and spec.loader:
                        spec.loader = ExporterModuleValidatedLoader(spec.loader)
                        return spec
            return None
        return None


def install() -> None:
    """
    Installs the ValidatingFinder for loading modules, called from package __init__.py
    """
    # idempotent insert
    for f in sys.meta_path:
        if isinstance(f, ValidatedFinder):
            return
    sys.meta_path.insert(0, ValidatedFinder())
