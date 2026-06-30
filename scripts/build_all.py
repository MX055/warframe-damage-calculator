import io
from contextlib import redirect_stderr, redirect_stdout

from build_arcanes import build_arcanes_json
from build_melees import build_melees_json
from build_mods import build_mods_json
from build_primaries import build_primaries_json
from build_secondaries import build_secondaries_json
from builder_helpers import OUTPUT_PATHS, write_json_file


def build_all() -> None:
    # Suppress all builder and helper prints for fully silent execution.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        write_json_file(OUTPUT_PATHS["melees"], build_melees_json())
        write_json_file(OUTPUT_PATHS["primaries"], build_primaries_json())
        write_json_file(OUTPUT_PATHS["secondaries"], build_secondaries_json())
        write_json_file(OUTPUT_PATHS["mods"], build_mods_json())
        write_json_file(OUTPUT_PATHS["arcanes"], build_arcanes_json())


if __name__ == "__main__":
    build_all()
