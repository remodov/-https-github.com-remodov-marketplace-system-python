#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K8S = ROOT / "deploy" / "k8s"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DOCKERFILES = ["services/catalog-starter/Dockerfile"]
BUILD_TOOLS = re.compile(r"\b(gcc|g\+\+|build-essential)\b")

problems: list[str] = []


def fail(where: str, what: str) -> None:
    problems.append(f"{where}: {what}")


def check_manifest(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    where = str(path.relative_to(ROOT))

    if "kind: Deployment" not in text:
        return

    for probe in ("readinessProbe", "livenessProbe"):
        if probe not in text:
            fail(where, f"нет {probe}: кластер не узнает, готов ли под")

    if "resources:" not in text:
        fail(where, "нет resources: под без лимитов может съесть узел")
    else:
        for section in ("requests:", "limits:"):
            if section not in text:
                fail(where, f"в resources нет {section}")

    if "runAsNonRoot: true" not in text:
        fail(where, "контейнер не помечен runAsNonRoot")

    image = re.search(r"image:\s*(\S+)", text)
    if not image:
        fail(where, "не указан image")
    elif ":" not in image.group(1).rsplit("/", 1)[-1]:
        fail(where, f"у образа {image.group(1)} нет тега: откатиться будет нечем")
    elif image.group(1).endswith(":latest"):
        fail(where, "тег latest: две выкатки дадут разные образы под одним именем")

    if "preStop" not in text:
        fail(where, "нет preStop: под уйдёт из балансировщика позже, чем перестанет отвечать")


def check_dockerfile(path: Path) -> None:
    if not path.is_file():
        fail(str(path), "файла нет")
        return
    text = path.read_text(encoding="utf-8")
    where = str(path.relative_to(ROOT))
    stages = re.split(r"(?m)^FROM\s", text)[1:]
    runtime = stages[-1] if stages else text

    if "USER " not in text:
        fail(where, "нет USER: контейнер побежит от root")
    if len(stages) < 2:
        fail(where, "сборка и запуск в одном слое: в образ уедут сборочные инструменты, кэш pip и лишние файлы")
    if re.search(r"FROM\s+\S+:latest", text):
        fail(where, "базовый образ с тегом latest")
    if BUILD_TOOLS.search(runtime):
        fail(where, "в рантайм-стадии стоят сборочные инструменты: gcc и build-essential нужны только стадии сборки")

    installs = "pip install" in runtime
    if installs and "--no-cache-dir" not in runtime:
        fail(where, "pip в рантайм-стадии ставит зависимости с кэшем: кэш колёс уедет в образ")
    elif not installs and "COPY --from=" not in runtime:
        fail(where, "рантайм-стадия ни ставит зависимости, ни берёт их из стадии сборки")


def check_workflow(path: Path) -> None:
    if not path.is_file():
        fail(str(path), "нет пайплайна")
        return
    text = path.read_text(encoding="utf-8")
    where = str(path.relative_to(ROOT))

    if "pytest" not in text:
        fail(where, "пайплайн не гоняет тесты сервисов")
    if "pull_request" not in text:
        fail(where, "пайплайн не запускается на pull request: сломанное вливается молча")
    if "check-deploy.py" not in text:
        fail(where, "пайплайн не проверяет манифесты")


def main() -> int:
    manifests = sorted(K8S.glob("*.yaml")) if K8S.is_dir() else []
    if not manifests:
        fail("deploy/k8s", "манифестов нет")
    for manifest in manifests:
        check_manifest(manifest)

    for dockerfile in DOCKERFILES:
        check_dockerfile(ROOT / dockerfile)

    check_workflow(WORKFLOW)

    if problems:
        print(f"Проблем: {len(problems)}")
        for problem in problems:
            print("  ✗", problem)
        return 1

    print(f"Проверено манифестов: {len(manifests)}, образов: {len(DOCKERFILES)}. Замечаний нет.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
