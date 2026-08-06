from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("control_tower_service.app:create_app", factory=True, host="0.0.0.0", port=8084)


if __name__ == "__main__":
    main()
