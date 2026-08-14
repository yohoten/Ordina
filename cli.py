"""
命令行接口 (CLI)
================
支持计划任务集成，无需 GUI 即可执行所有操作。
现已支持安卓手机文件管理。

用法:
  # PC 端
  python -m download_organizer.cli organize --path ~/Downloads
  python -m download_organizer.cli analyze --path ~/Downloads
  python -m download_organizer.cli cleanup --path ~/Downloads --dry-run
  python -m download_organizer.cli rename --path ~/Downloads --add-date-suffix
  python -m download_organizer.cli version

  # 安卓手机端
  python -m download_organizer.cli phone devices
  python -m download_organizer.cli phone info
  python -m download_organizer.cli phone organize --path /sdcard/Download
  python -m download_organizer.cli phone backup --remote /sdcard/DCIM --local D:/backup
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from organizer import FileOrganizer
from reporter import Reporter
from classifiers import PurposeClassifier


def cmd_organize(args):
    """执行文件整理"""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        print(f"[ERR] 路径不存在或不是目录: {path}")
        sys.exit(1)

    organizer = FileOrganizer(
        download_folder=path,
        mode=args.mode,
    )

    start = time.time()
    moved, duplicates = organizer.organize(
        dry_run=args.dry_run,
        use_date_grouping=args.date_grouping,
        add_date_suffix=args.add_date_suffix,
        use_number_prefix=not args.no_prefix,
    )

    elapsed = time.time() - start

    if args.output:
        reporter = Reporter()
        report_data = {
            "path": str(path),
            "mode": args.mode,
            "stats": organizer.stats,
            "moved_files": [{"from": o, "to": n} for o, n in moved],
            "duplicates_count": len(duplicates),
            "duration_seconds": elapsed,
        }
        out_path = Path(args.output)
        if out_path.suffix == ".json":
            reporter.to_json(report_data, out_path)
            print(f"[Doc] 报告已保存: {out_path}")
        elif out_path.suffix == ".csv":
            rows = [{"from": o, "to": n, "category": organizer.get_file_category(Path(n).parent)} for o, n in moved]
            reporter.to_csv(rows, out_path)
            print(f"[Doc] 报告已保存: {out_path}")

    if args.dry_run:
        print("\n[WARN]  预览模式完成。使用 --execute 执行实际操作。")
    else:
        print(f"\n[OK] 整理完成！耗时 {elapsed:.1f} 秒，移动 {organizer.stats['moved']} 个文件。")


def cmd_analyze(args):
    """分析目标目录"""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        print(f"[ERR] 路径不存在或不是目录: {path}")
        sys.exit(1)

    organizer = FileOrganizer(download_folder=path, mode=args.mode)
    analysis = organizer.analyze()
    reporter = Reporter()

    if args.format == "json":
        output = reporter.to_json(analysis, Path(args.output) if args.output else None)
        if not args.output:
            print(output)
    elif args.format == "markdown":
        output = reporter.to_markdown(analysis, Path(args.output) if args.output else None)
        if not args.output:
            print(output)
    else:
        # 默认文本格式
        print(reporter.operation_summary(
            stats=organizer.stats,
            moved_files=[],
            duplicates=analysis.get("duplicates", []),
            duration_seconds=0,
        ))
        print(organizer.archiver.format_report(analysis))


def cmd_cleanup(args):
    """清理临时文件和空目录"""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        print(f"[ERR] 路径不存在或不是目录: {path}")
        sys.exit(1)

    organizer = FileOrganizer(download_folder=path)
    result = organizer.cleanup(dry_run=args.dry_run)

    if args.dry_run:
        print("\n[WARN]  预览模式完成。使用 --execute 执行实际清理。")
    else:
        print(f"\n[OK] 清理完成！删除临时文件 {len(result['temp_files'])} 个，空目录 {len(result['empty_dirs'])} 个。")


def cmd_rename(args):
    """批量重命名文件"""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        print(f"[ERR] 路径不存在或不是目录: {path}")
        sys.exit(1)

    from normalizer import NameNormalizer
    normalizer = NameNormalizer()

    # 收集文件
    if args.recursive:
        files = [f for f in path.rglob("*") if f.is_file() and not f.name.startswith('.')]
    else:
        files = [f for f in path.iterdir() if f.is_file() and not f.name.startswith('.')]

    if args.add_date_suffix:
        preview = normalizer.preview_rename(files, add_date=True)
        print(f"\n[Note] 日期后缀预览 (共 {len(preview)} 个文件):")
        for orig, new_name in preview[:20]:
            print(f"   {orig.name} → {new_name}")
        if len(preview) > 20:
            print(f"   ... 还有 {len(preview) - 20} 个")

        if not args.dry_run and preview:
            results = normalizer.execute_rename(files, add_date=True, dry_run=False)
            print(f"\n[OK] 重命名完成！共 {len(results)} 个文件。")
            for orig, new in results[:10]:
                print(f"   {orig.name} → {new.name}")


def cmd_diagnose(args):
    """全面诊断"""
    path = Path(args.path).expanduser().resolve()
    if not path.is_dir():
        print(f"[ERR] 路径不存在或不是目录: {path}")
        sys.exit(1)

    organizer = FileOrganizer(download_folder=path, mode=args.mode)
    report = organizer.diagnose()

    if args.output:
        reporter = Reporter()
        output = reporter.to_json(report, Path(args.output))
        print(f"[Doc] 诊断报告已保存: {args.output}")
    else:
        print("\n诊断完成！使用 --output report.json 保存详细报告。")


def cmd_list_categories(args):
    """列出所有用途分类"""
    cats = PurposeClassifier.list_categories_with_info()
    print("\n📂 8大用途分类体系:\n")
    for cat, desc in cats:
        print(f"  {cat}")
        print(f"    {desc}")
        print()


def cmd_version(args):
    """显示版本"""
    try:
        from download_organizer import __version__
        print(f"Download Organizer v{__version__}")
    except ImportError:
        # 直接运行时获取版本
        import importlib.util
        init_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__init__.py")
        spec = importlib.util.spec_from_file_location("download_organizer_init", init_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print(f"Download Organizer v{mod.__version__}")


# ═══════════════════════════════════════════════════════════════
# 安卓手机命令实现
# ═══════════════════════════════════════════════════════════════


def _get_phone_organizer(args):
    """获取 PhoneOrganizer 实例"""
    from android import AdbBridge, PhoneOrganizer
    bridge = AdbBridge()
    bridge.select_device()
    mode = getattr(args, "mode", "purpose")
    return PhoneOrganizer(bridge, mode=mode)


def cmd_phone_devices(args):
    """列出手机设备"""
    from android import AdbBridge
    bridge = AdbBridge()

    print("\n📱 正在检测安卓设备...\n")
    devices = bridge.detect_devices(force_refresh=True)

    if not devices:
        print("❌ 未检测到任何设备。")
        print("\n请确保:")
        print("  1. 手机已通过 USB 连接电脑")
        print("  2. 已开启[开发者模式]和[USB 调试]")
        print("  3. 已在手机上授权 USB 调试")
        print("\n  或运行: adb devices")
        return

    if args.json:
        print(json.dumps([{
            "id": d.id, "state": d.state,
            "model": d.model, "manufacturer": d.manufacturer,
            "android": d.android_version,
        } for d in devices], indent=2, ensure_ascii=False))
        return

    print(f"找到 {len(devices)} 个设备:\n")
    for d in devices:
        state_icon = "✅" if d.state == "device" else "❌"
        auth_icon = "" if d.is_authorized else " (未授权)"
        print(f"  {state_icon} {d.model or d.id}{auth_icon}")
        print(f"     ID:       {d.id}")
        print(f"     状态:     {d.state}")
        if d.manufacturer:
            print(f"     制造商:   {d.manufacturer}")
        if d.android_version:
            print(f"     Android:  {d.android_version}")
        print()


def cmd_phone_info(args):
    """查看手机设备信息和存储概况"""
    from android import AdbBridge, PhoneOrganizer
    bridge = AdbBridge()
    bridge.select_device()

    organizer = PhoneOrganizer(bridge)
    summary = organizer.get_device_summary()

    if "error" in summary:
        print(f"\n❌ {summary['error']}\n")
        return

    print("\n" + "=" * 50)
    print("📱 手机设备信息")
    print("=" * 50)
    print(f"  设备:     {summary['device']}")
    print(f"  制造商:   {summary['manufacturer']}")
    print(f"  Android:  {summary['android']}")
    print(f"  电量:     {summary['battery']}")
    print()
    print(f"  存储:")
    print(f"    总容量: {summary['storage']['total']}")
    print(f"    可用:   {summary['storage']['free']}")
    print(f"    使用率: {summary['storage']['usage']}")
    print(f"    下载目录: {summary['download_size']}")
    print(f"    相册目录: {summary['dcim_size']}")

    # 存储告警
    usage_str = summary['storage']['usage']
    usage_num = 0
    if isinstance(usage_str, str) and '%' in usage_str:
        try:
            usage_num = int(usage_str.replace('%', '').strip())
        except ValueError:
            pass
    if usage_num > 85:
        print(f"\n  ⚠️  存储空间即将用尽 ({usage_num}%)，建议清理")
    elif usage_num > 70:
        print(f"\n  ⚠️  存储空间占用较高 ({usage_num}%)")
    print()


def cmd_phone_organize(args):
    """整理手机目录"""
    organizer = _get_phone_organizer(args)
    dry_run = getattr(args, "dry_run", True)

    path = args.path
    print(f"\n📱 整理手机目录: {path}")
    print(f"   模式: {'预览' if dry_run else '执行'}")
    print()

    result = organizer.organize(
        remote_path=path,
        dry_run=dry_run,
        max_depth=args.depth,
        use_date_grouping=args.date_grouping,
        add_date_suffix=args.add_date_suffix,
    )

    stats = result["stats"]
    print(f"\n✅ 完成! 扫描 {stats['scanned']} 个文件, "
          f"移动 {stats['moved']} 个, "
          f"错误 {stats['errors']} 个")


def cmd_phone_cleanup(args):
    """清理手机临时文件"""
    organizer = _get_phone_organizer(args)
    dry_run = getattr(args, "dry_run", True)

    print(f"\n🗑️  清理手机目录: {args.path}")
    print(f"   模式: {'预览' if dry_run else '执行'}")
    print()

    result = organizer.cleanup(
        remote_path=args.path,
        dry_run=dry_run,
    )

    print(f"\n   临时文件: {len(result['temp_files_removed'])} 个")
    print(f"   空目录:   {len(result['empty_dirs_removed'])} 个")

    if result["temp_files_removed"][:10]:
        print("\n   临时文件列表 (前10个):")
        for f in result["temp_files_removed"][:10]:
            print(f"     - {f}")

    print(f"\n✅ 清理完成!")


def cmd_phone_backup(args):
    """备份手机文件到电脑"""
    organizer = _get_phone_organizer(args)
    dry_run = getattr(args, "dry_run", True)

    print(f"\n📦 手机备份: {args.remote}")
    print(f"   -> 电脑:  {args.local}")
    print(f"   模式:   {'预览' if dry_run else '执行'}")
    if args.ext:
        print(f"   类型:   {', '.join(args.ext)}")
    print()

    result = organizer.backup_to_pc(
        remote_source=args.remote,
        local_target=args.local,
        organize_after_backup=args.organize,
        dry_run=dry_run,
        file_extensions=args.ext,
    )

    if result.get("pulled_directory"):
        print(f"\n✅ 目录备份完成!")
    else:
        files = result.get("pulled_files", [])
        total_size = sum(f.get("size", 0) for f in files)
        print(f"\n✅ 备份完成! {len(files)} 个文件, "
              f"共 {total_size / (1024*1024):.1f} MB")

    if result.get("organized"):
        print(f"   📂 备份文件已在电脑端自动整理")

    if result.get("errors"):
        print(f"\n⚠️  {len(result['errors'])} 个错误:")
        for e in result["errors"][:5]:
            print(f"   - {e}")


def cmd_phone_scan(args):
    """扫描手机文件"""
    from android import AdbBridge, PhoneScanner
    bridge = AdbBridge()
    bridge.select_device()
    scanner = PhoneScanner(bridge)

    print(f"\n🔍 扫描手机目录: {args.path}")
    print(f"   深度: {args.depth}")
    if args.ext:
        print(f"   类型: {', '.join(args.ext)}")
    if args.large:
        print(f"   大文件: >{args.large}MB")
    print()

    if args.large > 0:
        result = scanner.find_large_files(args.path, min_size_mb=args.large, max_depth=args.depth)
    else:
        exts = []
        if args.ext:
            exts = [f".{e.lstrip('.')}" for e in args.ext]
        result = scanner.scan_directory(
            args.path,
            max_depth=args.depth,
            file_extensions=exts,
        )

    summary = scanner.summarize(result)

    print(f"   文件数: {summary['total_files']}")
    print(f"   目录数: {summary['total_dirs']}")
    print(f"   总大小: {summary['total_size_formatted']}")
    print(f"   耗时:   {summary['elapsed_seconds']}秒")
    print()

    if summary["top_extensions"]:
        print("   扩展名 Top 10:")
        for ext_info in summary["top_extensions"]:
            print(f"     {ext_info['ext']:10s}  {ext_info['count']:5d} 个  "
                  f"{ext_info['size']/(1024*1024):8.1f} MB")
        print()

    # 大文件列表
    if args.large > 0 and result.files:
        print(f"   大文件列表 (>{args.large}MB):")
        for f in result.files[:20]:
            print(f"     {f.name:40s}  {f.size/(1024*1024):.1f} MB")
        if len(result.files) > 20:
            print(f"     ... 还有 {len(result.files) - 20} 个")

    # 导出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fp:
            json.dump(summary, fp, indent=2, ensure_ascii=False)
        print(f"\n💾 扫描结果已保存: {args.output}")


def cmd_phone_diagnose(args):
    """全面诊断手机文件状况"""
    organizer = _get_phone_organizer(args)

    print(f"\n🔬 全面诊断手机存储...\n")
    report = organizer.diagnose()

    # 设备信息
    dev = report.get("device_info", {})
    if dev:
        print(f"  设备: {dev.get('model', '未知')} ({dev.get('manufacturer', '')})")
        print(f"  Android: {dev.get('android_version', '未知')}")
        print(f"  电量: {dev.get('battery_level', '未知')}%")

    # 存储
    storage = report.get("storage", {})
    if storage:
        free_gb = storage.get("internal_free", 0) / (1024**3)
        total_gb = storage.get("internal_total", 0) / (1024**3)
        if total_gb > 0:
            print(f"\n  存储: {free_gb:.1f}GB / {total_gb:.1f}GB 可用")

    # 主要目录
    dirs = report.get("top_directories", [])
    if dirs:
        print(f"\n  主要目录占用:")
        for d in dirs[:10]:
            print(f"    {d['name']:12s}  {d['files']:5d} 个  {d['size_formatted']:>8s}")

    # 大文件
    large = report.get("large_files", [])
    if large:
        print(f"\n  大文件 (>100MB): {len(large)} 个")
        for f in large[:10]:
            print(f"    {f['name']:40s}  {f['size_mb']:8.1f} MB")

    # 建议
    recs = report.get("recommendations", [])
    if recs:
        print(f"\n  💡 建议:")
        for r in recs:
            print(f"    {r}")

    # 导出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fp:
            json.dump(report, fp, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 诊断报告已保存: {args.output}")

    print()


def cmd_phone_reconnect(args):
    """重新连接 USB 设备"""
    from android import AdbBridge
    bridge = AdbBridge()

    print("\n🔄 重新连接 USB 设备...")
    if bridge.reconnect():
        print("✅ 已重新连接\n")
    else:
        print("⚠️  重连失败，尝试重启 ADB 服务...")
        bridge.restart_server()
        if bridge.wait_for_device(timeout_seconds=15):
            print("✅ ADB 服务已重启，设备已连接\n")
        else:
            print("❌ 无法连接到设备，请检查 USB 连接\n")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="[Folder] 下载文件夹整理工具 v2.0 -- 支持 PC 和安卓手机",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # PC 端操作
  %(prog)s organize --path ~/Downloads                    # 预览整理
  %(prog)s analyze --path ~/Downloads --format markdown   # 生成分析报告

  # 安卓手机操作
  %(prog)s phone devices                                   # 列出连接的手机设备
  %(prog)s phone info                                      # 查看手机信息
  %(prog)s phone organize --path /sdcard/Download          # 预览整理手机下载目录
  %(prog)s phone organize --path /sdcard/Download --execute # 执行整理
  %(prog)s phone cleanup --path /sdcard/Download           # 清理手机临时文件
  %(prog)s phone backup --remote /sdcard/DCIM --local ./backup  # 备份手机相册到电脑
  %(prog)s phone diagnose                                  # 全面诊断手机存储
  %(prog)s phone scan --path /sdcard --ext .apk           # 扫描手机 APK 文件
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ═══════════════════════════════════════════════════════════
    # PC 端命令
    # ═══════════════════════════════════════════════════════════

    # -- organize --
    org_parser = subparsers.add_parser("organize", help="整理文件")
    org_parser.add_argument("--path", "-p", required=True, help="目标文件夹路径")
    org_parser.add_argument("--mode", "-m", choices=["extension", "purpose"],
                            default="purpose", help="分类模式 (默认: purpose)")
    org_parser.add_argument("--execute", action="store_true",
                            help="实际执行（取消预览模式）")
    org_parser.add_argument("--date-grouping", action="store_true",
                            help="按日期子目录分组")
    org_parser.add_argument("--add-date-suffix", action="store_true",
                            help="文件添加日期后缀 (_YYYYMMDD)")
    org_parser.add_argument("--no-prefix", action="store_true",
                            help="禁用数字前缀")
    org_parser.add_argument("--output", "-o", help="导出报告路径 (.json/.csv)")

    # -- analyze --
    ana_parser = subparsers.add_parser("analyze", help="分析目标目录")
    ana_parser.add_argument("--path", "-p", required=True, help="目标文件夹路径")
    ana_parser.add_argument("--mode", "-m", choices=["extension", "purpose"],
                            default="purpose", help="分类模式")
    ana_parser.add_argument("--format", "-f", choices=["text", "json", "markdown"],
                            default="text", help="输出格式 (默认: text)")
    ana_parser.add_argument("--output", "-o", help="导出报告路径")

    # -- cleanup --
    cln_parser = subparsers.add_parser("cleanup", help="清理临时文件和空目录")
    cln_parser.add_argument("--path", "-p", required=True, help="目标文件夹路径")
    cln_parser.add_argument("--execute", action="store_true",
                            help="实际执行（取消预览模式）")

    # -- rename --
    rnm_parser = subparsers.add_parser("rename", help="批量重命名")
    rnm_parser.add_argument("--path", "-p", required=True, help="目标文件夹路径")
    rnm_parser.add_argument("--add-date-suffix", action="store_true",
                            help="添加日期后缀")
    rnm_parser.add_argument("--recursive", "-r", action="store_true",
                            help="递归处理子目录")
    rnm_parser.add_argument("--execute", action="store_true",
                            help="实际执行（取消预览模式）")

    # -- diagnose --
    diag_parser = subparsers.add_parser("diagnose", help="全面诊断")
    diag_parser.add_argument("--path", "-p", required=True, help="目标文件夹路径")
    diag_parser.add_argument("--mode", "-m", choices=["extension", "purpose"],
                             default="purpose", help="分类模式")
    diag_parser.add_argument("--output", "-o", help="导出诊断报告 (.json)")

    # -- categories --
    subparsers.add_parser("categories", help="列出用途分类体系")

    # -- version --
    subparsers.add_parser("version", help="显示版本信息")

    # ═══════════════════════════════════════════════════════════
    # 安卓手机命令
    # ═══════════════════════════════════════════════════════════
    phone_parser = subparsers.add_parser("phone", help="📱 安卓手机文件管理")
    phone_sub = phone_parser.add_subparsers(dest="phone_command", help="手机操作命令")

    # -- phone devices --
    p_devices = phone_sub.add_parser("devices", help="列出已连接的手机设备")
    p_devices.add_argument("--json", action="store_true", help="JSON 格式输出")

    # -- phone info --
    phone_sub.add_parser("info", help="查看手机设备信息和存储概况")

    # -- phone organize --
    p_org = phone_sub.add_parser("organize", help="整理手机目录")
    p_org.add_argument("--path", default="/sdcard/Download",
                       help="手机目标目录 (默认: /sdcard/Download)")
    p_org.add_argument("--mode", choices=["extension", "purpose"],
                       default="purpose", help="分类模式 (默认: purpose)")
    p_org.add_argument("--execute", action="store_true",
                       help="实际执行（取消预览模式）")
    p_org.add_argument("--date-grouping", action="store_true",
                       help="按日期子目录分组")
    p_org.add_argument("--add-date-suffix", action="store_true",
                       help="文件添加日期后缀")
    p_org.add_argument("--depth", type=int, default=0,
                       help="扫描深度 (0=仅当前目录, -1=无限)")

    # -- phone cleanup --
    p_cln = phone_sub.add_parser("cleanup", help="清理手机临时文件和空目录")
    p_cln.add_argument("--path", default="/sdcard/Download",
                       help="手机目标目录 (默认: /sdcard/Download)")
    p_cln.add_argument("--execute", action="store_true",
                       help="实际执行（取消预览模式）")

    # -- phone backup --
    p_bak = phone_sub.add_parser("backup", help="备份手机文件到电脑")
    p_bak.add_argument("--remote", "-r", required=True,
                       help="手机源目录 (如 /sdcard/DCIM/Camera)")
    p_bak.add_argument("--local", "-l", required=True,
                       help="电脑目标目录")
    p_bak.add_argument("--organize", action="store_true",
                       help="备份后在电脑上自动整理")
    p_bak.add_argument("--execute", action="store_true",
                       help="实际执行（取消预览模式）")
    p_bak.add_argument("--ext", nargs="*",
                       help="仅备份指定扩展名 (如 .jpg .mp4)")

    # -- phone scan --
    p_scan = phone_sub.add_parser("scan", help="扫描手机文件")
    p_scan.add_argument("--path", default="/sdcard",
                        help="扫描目录 (默认: /sdcard)")
    p_scan.add_argument("--ext", nargs="*",
                        help="按扩展名过滤 (如 .apk .jpg)")
    p_scan.add_argument("--large", type=int, default=0,
                        help="查找大于指定 MB 的文件")
    p_scan.add_argument("--depth", type=int, default=2,
                        help="扫描深度 (默认: 2)")
    p_scan.add_argument("--output", "-o", help="导出扫描结果 (.json)")

    # -- phone diagnose --
    p_diag = phone_sub.add_parser("diagnose", help="全面诊断手机文件状况")
    p_diag.add_argument("--output", "-o", help="导出诊断报告 (.json)")

    # -- phone reconnect --
    phone_sub.add_parser("reconnect", help="重新连接 USB 设备")

    args = parser.parse_args()

    # 统一处理 dry_run / execute 转换
    if hasattr(args, "execute") and args.execute:
        args.dry_run = False
    elif hasattr(args, "execute"):
        args.dry_run = True

    # 分发命令
    commands = {
        "organize": cmd_organize,
        "analyze": cmd_analyze,
        "cleanup": cmd_cleanup,
        "rename": cmd_rename,
        "diagnose": cmd_diagnose,
        "categories": cmd_list_categories,
        "version": cmd_version,
    }

    phone_commands = {
        "devices": cmd_phone_devices,
        "info": cmd_phone_info,
        "organize": cmd_phone_organize,
        "cleanup": cmd_phone_cleanup,
        "backup": cmd_phone_backup,
        "scan": cmd_phone_scan,
        "diagnose": cmd_phone_diagnose,
        "reconnect": cmd_phone_reconnect,
    }

    if args.command == "phone":
        if hasattr(args, "phone_command") and args.phone_command in phone_commands:
            phone_commands[args.phone_command](args)
        else:
            phone_parser.print_help()
    elif args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
