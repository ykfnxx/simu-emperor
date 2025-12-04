"""
测试简化版实时CLI

测试刷新但不自动刷新的功能
"""

from core.game import Game
from ui.cli_realtime import RealtimeGameCLI
import sys


def test_realtime_cli():
    """测试简化版实时CLI"""
    print("正在初始化游戏和实时CLI（简化版）...")

    # 创建游戏实例
    game = Game(db_path="test_realtime_simple.db")

    # 创建CLI并只运行3次循环做测试
    cli = RealtimeGameCLI(game)

    # 手动调用几次绘制来测试刷新功能
    print("\n✓ 测试1: 绘制初始仪表盘")
    cli.draw_dashboard()
    input("\n按Enter继续测试...")

    print("\n✓ 测试2: 再次绘制仪表盘（验证刷新）")
    cli.draw_dashboard()
    input("\n按Enter完成测试...")

    print("\n✓ 测试通过！简化版实时CLI工作正常。")


if __name__ == "__main__":
    try:
        test_realtime_cli()
    except KeyboardInterrupt:
        print("\n\n测试已中断")
    except Exception as e:
        print(f"\n\n测试错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
