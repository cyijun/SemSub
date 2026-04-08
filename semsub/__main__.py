"""
SemSub 模块入口

支持多种启动方式：
- python -m semsub (默认 CLI)
- python -m semsub.cli (CLI)
- python -m semsub.gui.app (PyQt6 GUI)
- python -m semsub.gradio_gui (Gradio GUI)
"""

import sys

if len(sys.argv) > 1 and sys.argv[1] == "--gradio":
    # 启动 Gradio GUI
    sys.argv.pop(1)  # 移除 --gradio 参数
    from semsub.gradio_gui.app import main
    main()
elif len(sys.argv) > 1 and sys.argv[1] == "--gui":
    # 启动 PyQt6 GUI
    sys.argv.pop(1)  # 移除 --gui 参数
    from semsub.gui.app import main
    main()
else:
    # 默认启动 CLI
    from semsub.cli.main import cli
    cli()
