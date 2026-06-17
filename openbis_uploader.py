"""
openBIS upload logic for LEDSS Session Logger v1.0.
Credentials are supplied at session start via a login dialog — never saved to disk.
Uploads only to experiments that already exist on the server.
"""

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from pybis import Openbis
except ImportError:
    Openbis = None


def list_data_files(folder: Path, extensions: list[str]) -> list[Path]:
    exts = {e.lower() for e in extensions}
    if not folder.is_dir():
        return []
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in exts
    )


def is_file_stable(filepath: Path, checks: int = 3, interval: float = 1.0) -> bool:
    if not filepath.exists():
        return False
    sizes = []
    for _ in range(checks):
        try:
            sizes.append(filepath.stat().st_size)
        except OSError:
            return False
        time.sleep(interval)
    return len(set(sizes)) == 1 and sizes[0] > 0


def check_files_stable(files: list[Path], checks: int = 3, interval: float = 1.0) -> tuple[bool, list[Path]]:
    unstable = [f for f in files if not is_file_stable(f, checks=checks, interval=interval)]
    return (len(unstable) == 0, unstable)


class OpenBISUploader:
    """Connects to openBIS and uploads session data files."""

    def __init__(self, config: dict):
        self.cfg = config["openbis"]
        self.upload_cfg = config["upload"]
        self._o: Optional[Openbis] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self.last_error = ""

    @staticmethod
    def dependencies_available() -> bool:
        return Openbis is not None

    @property
    def username(self) -> str:
        return self._username or ""

    def connect(self, username: str, password: str) -> bool:
        if Openbis is None:
            logger.error("pybis is not installed — run: pip install -r requirements.txt")
            return False
        try:
            self._username = username.strip()
            self._password = password
            self.last_error = ""
            self._o = Openbis(
                self.cfg["url"],
                verify_certificates=self.cfg.get("verify_ssl", True),
            )
            self._o.login(self._username, self._password, save_token=False)
            logger.info("openBIS connected as '%s'", self._username)
            return True
        except Exception as exc:
            self.last_error = str(exc).strip() or exc.__class__.__name__
            logger.error("openBIS connection error: %s", self.last_error)
            self._clear_credentials()
            self._o = None
            return False

    def disconnect(self):
        if self._o and self._o.is_session_active():
            try:
                self._o.logout()
            except Exception:
                pass
            logger.info("openBIS session closed")
        self._o = None
        self._clear_credentials()

    def _clear_credentials(self):
        self._username = None
        self._password = None

    def ensure_connected(self) -> bool:
        return self._ensure_connected()

    def _ensure_connected(self) -> bool:
        if self._o is not None and self._o.is_session_active():
            return True
        if not self._username or not self._password:
            return False
        logger.warning("openBIS session expired — reconnecting")
        return self.connect(self._username, self._password)

    def _entity_code(self, entity) -> str:
        code = getattr(entity, "code", None)
        if code:
            return str(code)
        ident = getattr(entity, "identifier", None) or getattr(entity, "permId", None)
        if ident and "/" in str(ident):
            return str(ident).rstrip("/").split("/")[-1]
        return str(ident or entity)

    def experiment_path(self, destination: dict) -> str:
        path = destination.get("experiment_path", "").strip()
        if path:
            return path
        return "/{space}/{project}/{experiment}".format(**destination)

    def list_projects(self, space: str) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            projects = self._o.get_projects(space=space)
            results = []
            seen = set()
            for project in projects:
                code = self._entity_code(project)
                if not code or code in seen:
                    continue
                seen.add(code)
                path = f"/{space}/{code}"
                results.append({
                    "code": code,
                    "path": path,
                    "label": f"{code}  ({path})",
                })
            results.sort(key=lambda p: p["code"].lower())
            logger.info("Found %d project(s) in %s", len(results), space)
            return results
        except Exception as exc:
            logger.error("Could not list projects for %s: %s", space, exc)
            return []

    def list_experiments(self, space: str, project: str) -> list[dict]:
        if not self._ensure_connected() or not project:
            return []
        try:
            experiments = self._o.get_experiments(space=space, project=project)
            results = []
            seen = set()
            for experiment in experiments:
                code = self._entity_code(experiment)
                if not code or code in seen:
                    continue
                seen.add(code)
                ident = getattr(experiment, "identifier", None)
                ident = str(ident).rstrip("/") if ident else f"/{space}/{project}/{code}"
                name = getattr(experiment, "name", None) or code
                results.append({
                    "code": code,
                    "identifier": ident,
                    "name": name,
                    "label": f"{name}  ({ident})",
                })
            results.sort(key=lambda e: e["name"].lower())
            logger.info(
                "Found %d experiment(s) in /%s/%s", len(results), space, project
            )
            return results
        except Exception as exc:
            logger.error(
                "Could not list experiments for /%s/%s: %s", space, project, exc
            )
            return []

    def resolve_experiment(self, destination: dict):
        path = self.experiment_path(destination)
        try:
            return self._o.get_experiment(path)
        except Exception as exc:
            self.last_error = f"Experiment not found: {path} ({exc})"
            logger.error(self.last_error)
            return None

    def existing_dataset_names(self, experiment) -> set[str]:
        """Names already used on this experiment (dataset $name / files)."""
        names: set[str] = set()
        try:
            datasets = experiment.get_datasets()
        except Exception as exc:
            logger.warning("Could not list datasets for duplicate check: %s", exc)
            return names

        for dataset in datasets:
            props = getattr(dataset, "props", None)
            if props is not None:
                for getter in (
                    lambda: props.get("$name") if hasattr(props, "get") else None,
                    lambda: props.get("NAME") if hasattr(props, "get") else None,
                    lambda: getattr(props, "$name", None),
                    lambda: getattr(props, "NAME", None),
                ):
                    try:
                        value = getter()
                        if value:
                            names.add(str(value).strip().lower())
                    except Exception:
                        pass
                try:
                    if hasattr(props, "all"):
                        for key, value in props.all().items():
                            if value and key.upper() in ("$NAME", "NAME"):
                                names.add(str(value).strip().lower())
                except Exception:
                    pass

            for entry in getattr(dataset, "file_list", None) or []:
                filename = str(entry).replace("\\", "/").split("/")[-1]
                if not filename:
                    continue
                names.add(filename.lower())
                stem = Path(filename).stem
                if stem:
                    names.add(stem.lower())
        return names

    def find_duplicate_uploads(self, files: list[Path], experiment) -> list[str]:
        existing = self.existing_dataset_names(experiment)
        if not existing:
            return []
        duplicates = []
        for filepath in files:
            stem = filepath.stem.lower()
            if stem in existing or filepath.name.lower() in existing:
                duplicates.append(filepath.name)
        return duplicates

    def upload_file(self, filepath: Path, experiment) -> bool:
        if not self._ensure_connected():
            return False
        try:
            dataset = self._o.new_dataset(
                type=self.upload_cfg["dataset_type"],
                experiment=experiment,
                files=[str(filepath)],
                props={"$name": filepath.stem},
            )
            dataset.save()
            logger.info(
                "Uploaded %s → %s (permID: %s)",
                filepath.name,
                getattr(experiment, "identifier", experiment),
                dataset.permId,
            )
            return True
        except Exception as exc:
            logger.error("Upload failed for '%s': %s", filepath.name, exc)
            return False

    def upload_session_files(
        self,
        folder: Path,
        destination: dict,
        extensions: list[str],
    ) -> dict:
        results = {
            "ok": 0,
            "error": 0,
            "files_ok": [],
            "files_error": [],
            "duplicates": [],
            "status": "Skipped",
        }

        files = list_data_files(folder, extensions)
        if not files:
            results["status"] = "No files"
            return results

        stable, unstable = check_files_stable(files)
        if not stable:
            names = ", ".join(f.name for f in unstable)
            results["status"] = f"Unstable: {names}"
            return results

        if not self._ensure_connected():
            results["status"] = "Connection failed"
            return results

        experiment = self.resolve_experiment(destination)
        if experiment is None:
            results["status"] = "Experiment not found"
            if self.last_error:
                results["error_detail"] = self.last_error
            return results

        duplicates = self.find_duplicate_uploads(files, experiment)
        if duplicates:
            results["status"] = "Duplicate"
            results["duplicates"] = duplicates
            results["error_detail"] = (
                "Already on openBIS in this experiment: " + ", ".join(duplicates)
            )
            logger.error(results["error_detail"])
            return results

        for filepath in files:
            if self.upload_file(filepath, experiment):
                results["ok"] += 1
                results["files_ok"].append(filepath.name)
                self._maybe_move(filepath)
            else:
                results["error"] += 1
                results["files_error"].append(filepath.name)

        if results["ok"] and not results["error"]:
            results["status"] = "OK"
        elif results["ok"]:
            results["status"] = "Partial"
        else:
            results["status"] = "Failed"
        return results

    def _maybe_move(self, filepath: Path):
        if not self.upload_cfg.get("move_after_upload", False):
            return
        dest_dir = filepath.parent / self.upload_cfg.get("uploaded_subfolder", "uploaded")
        dest_dir.mkdir(exist_ok=True)
        filepath.rename(dest_dir / filepath.name)


def setup_upload_logging(log_file: str):
    if not log_file:
        return
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
