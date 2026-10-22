"""Antarmuka baris perintah: python -m dsx build|check|scaffold|presets|model PATH.

Kode keluar: 0 berhasil, 1 dokumen/diagnostik gagal, 2 kesalahan penggunaan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import LANGUAGE_VERSION, __version__
from .api.service import GenerationResult, generate_from_directory
from .renderers.base import SUPPORTED_FORMATS


def _resolve_target(path: str) -> tuple[Path, str] | None:
    target = Path(path)
    if target.is_dir():
        return target, "document.dsx"
    if target.suffix.lower() == ".dsx":
        return (target.parent if str(target.parent) else Path(".")), target.name
    return None


_EXT_FMT = {".docx": "docx", ".pdf": "pdf", ".html": "html"}


def _fix_output(output: str | None, fmt: str, default_dir: Path, stem: str) -> str:
    """Tentukan path keluaran: tambah ekstensi bila hilang, isi direktori bila -o berupa folder."""
    ext = "." + fmt
    if not output:
        return str(default_dir / (stem + ext))
    out = Path(output)
    if out.is_dir() or output.endswith(("/", "\\")):
        return str(out / (stem + ext))
    if not out.suffix:
        out = out.with_name(out.name + ext)
    try:
        out.resolve().parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return str(out)


def _report(result: GenerationResult, as_json: bool) -> None:
    if as_json:
        payload = {
            "ok": result.ok,
            "status": result.status,
            "output_file": result.output_file,
            "diagnostics": [d.to_dict() for d in result.diagnostics],
            "warnings": [d.to_dict() for d in result.warnings],
            "render_summary": result.render_summary,
            "referenced_files": result.referenced_files,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for d in result.diagnostics:
        print(d.format(), file=sys.stderr)
    for w in result.warnings:
        print(w.format(), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dsx", description="DocScript AI (DSX) engine")
    parser.add_argument(
        "--version",
        action="version",
        version=f"dsx {__version__} (bahasa DSX {LANGUAGE_VERSION})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("build", "check"):
        p = sub.add_parser(name, help="bangun dokumen" if name == "build" else "validasi tanpa rendering")
        p.add_argument("path", help="direktori proyek (berisi document.dsx) atau file .dsx")
        p.add_argument("--json", action="store_true", help="keluaran diagnostik dalam JSON")
        if name == "build":
            p.add_argument("-o", "--output", help="berkas keluaran")
            p.add_argument("--format", default="docx", choices=list(SUPPORTED_FORMATS), help="format keluaran")
            p.add_argument("--no-overwrite", action="store_true", help="jangan timpa file yang sudah ada")

    p_sc = sub.add_parser("scaffold", help="buat kerangka proyek akademik")
    p_sc.add_argument("name", choices=("makalah", "skripsi", "laporan", "praktikum", "artikel"))
    p_sc.add_argument("-d", "--dir", default=".")
    p_sc.add_argument("--title", default="Judul Dokumen")
    p_sc.add_argument("--author", default="Penulis")
    p_sc.add_argument("--json", action="store_true")

    p_pr = sub.add_parser("presets", help="tampilkan daftar preset")
    p_pr.add_argument("--json", action="store_true")

    p_md = sub.add_parser("model", help="compile ke Document Model JSON")
    p_md.add_argument("path", help="direktori proyek atau file .dsx")

    p_uf = sub.add_parser("update-fields", help="perbarui field TOC/daftar via LibreOffice")
    p_uf.add_argument("docx", help="berkas .docx")
    p_uf.add_argument("-o", "--output", help="keluaran (default: timpa input)")

    # --- Form mode (v1.3) ---
    p_schema = sub.add_parser("schema", help="export skema bahasa DSX (JSON) untuk editor/autocomplete")
    p_schema.add_argument("-o", "--output", help="tulis ke file (default: stdout)")

    p_form = sub.add_parser("form", help="mode formulir: default|validate|generate|ui-schema")
    form_sub = p_form.add_subparsers(dest="form_cmd", required=True)

    p_fd = form_sub.add_parser("default", help="cetak form.json default")
    p_fd.add_argument("--kind", default="surat-resmi", choices=("surat-resmi", "laporan", "makalah", "custom"))
    p_fd.add_argument("-o", "--output", help="tulis ke file")

    p_fv = form_sub.add_parser("validate", help="validasi form.json")
    p_fv.add_argument("form", help="path form.json")
    p_fv.add_argument("--json", action="store_true")

    p_fg = form_sub.add_parser("generate", help="form.json → document.dsx (+ opsional build)")
    p_fg.add_argument("form", help="path form.json")
    p_fg.add_argument("-d", "--dir", default=".", help="direktori keluaran proyek")
    p_fg.add_argument("-o", "--output", help="nama file .dsx (default: document.dsx)")
    p_fg.add_argument("--build", action="store_true", help="langsung build DOCX setelah generate")
    p_fg.add_argument("--format", default="docx", choices=list(SUPPORTED_FORMATS))
    p_fg.add_argument("--json", action="store_true")

    p_fu = form_sub.add_parser("ui-schema", help="skema field UI untuk jenis form")
    p_fu.add_argument("--kind", default="surat-resmi", choices=("surat-resmi", "laporan", "makalah", "custom"))
    p_fu.add_argument("-o", "--output", help="tulis ke file")

    p_fb = form_sub.add_parser("blocks", help="katalog tipe blok (form kustom)")
    p_fb.add_argument("--json", action="store_true")

    p_fp = form_sub.add_parser("preset", help="buat form custom dari preset struktur")
    p_fp.add_argument("name", choices=("surat-resmi", "laporan-singkat", "makalah", "kosong"))
    p_fp.add_argument("-o", "--output", help="tulis form.json")

    p_fc = form_sub.add_parser("convert", help="konversi form surat-resmi → custom blocks")
    p_fc.add_argument("form", help="form.json sumber")
    p_fc.add_argument("-o", "--output", help="keluaran form custom")

    p_up = form_sub.add_parser("user-preset", help="kelola preset pengguna di folder proyek")
    up_sub = p_up.add_subparsers(dest="up_cmd", required=True)
    up_save = up_sub.add_parser("save", help="simpan form.json sebagai preset")
    up_save.add_argument("name", help="nama preset (huruf/angka/-/_)")
    up_save.add_argument("form", help="path form.json")
    up_save.add_argument("-d", "--dir", default=".", help="direktori proyek")
    up_save.add_argument("--desc", default="", help="deskripsi singkat")
    up_save.add_argument("--no-overwrite", action="store_true")
    up_list = up_sub.add_parser("list", help="daftar preset pengguna")
    up_list.add_argument("-d", "--dir", default=".")
    up_list.add_argument("--json", action="store_true")
    up_load = up_sub.add_parser("load", help="muat preset ke stdout atau file")
    up_load.add_argument("name")
    up_load.add_argument("-d", "--dir", default=".")
    up_load.add_argument("-o", "--output", help="tulis ke file")
    up_del = up_sub.add_parser("delete", help="hapus preset")
    up_del.add_argument("name")
    up_del.add_argument("-d", "--dir", default=".")

    p_comp = form_sub.add_parser("completions", help="export data autocomplete mode kode (JSON)")
    p_comp.add_argument("-o", "--output", help="tulis ke file")

    p_d2f = form_sub.add_parser("dsx-to-form", help="konversi document.dsx → form custom (best-effort)")
    p_d2f.add_argument("dsx", help="file .dsx")
    p_d2f.add_argument("-o", "--output", help="keluaran form.json")
    p_d2f.add_argument("--json", action="store_true")

    p_fmt = form_sub.add_parser("format", help="format sumber .dsx (indent)")
    p_fmt.add_argument("dsx", help="file .dsx")
    p_fmt.add_argument("-o", "--output", help="keluaran (default: timpa input)")
    p_fmt.add_argument("--stdout", action="store_true", help="cetak ke stdout")

    p_fs = form_sub.add_parser("serve", help="server lokal: UI form + generate + build + upload")
    p_fs.add_argument("-d", "--dir", default=".", help="direktori proyek (form.json, assets, output)")
    p_fs.add_argument("--host", default="127.0.0.1")
    p_fs.add_argument("--port", type=int, default=8765)
    p_fs.add_argument("--ui", help="folder HTML UI (default: form-ui di sumber)")

    args = parser.parse_args(argv)

    if args.command == "schema":
        from .form.schema_export import export_language_schema
        payload = export_language_schema()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
            print(f"OK: schema → {args.output}")
        else:
            print(text)
        return 0

    if args.command == "form":
        return _cmd_form(args)

    if args.command == "presets":
        from .presets import list_presets
        data = list_presets()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for k, v in data.items():
                print(f"{k}: {', '.join(v)}")
        return 0

    if args.command == "scaffold":
        from .scaffold import write_scaffold
        path = write_scaffold(args.dir, args.name, title=args.title, author=args.author)
        if args.json:
            print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False))
        else:
            print(f"OK: kerangka ditulis ke {path}")
        return 0

    if args.command == "update-fields":
        from .update_fields import update_fields
        try:
            out = update_fields(args.docx, args.output)
            print(f"OK: field diperbarui → {out}")
            return 0
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "model":
        resolved = _resolve_target(args.path)
        if resolved is None:
            print(f"ERROR: path tidak valid: {args.path}", file=sys.stderr)
            return 2
        project_dir, dsx_name = resolved
        from .api.service import compile_to_model
        text = (project_dir / dsx_name).read_text(encoding="utf-8")
        files = {}
        for f in project_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".txt", ".csv", ".png", ".jpg", ".jpeg"):
                try:
                    files[str(f.relative_to(project_dir)).replace("\\", "/")] = f.read_bytes()
                except Exception:
                    pass
        model, result = compile_to_model(text, files=files, source_name=dsx_name)
        if not result.ok:
            _report(result, True)
            return 1
        print(json.dumps(model.to_dict() if model else {}, ensure_ascii=False, indent=2))
        return 0

    resolved = _resolve_target(args.path)
    if resolved is None:
        print(f"ERROR: argumen harus berupa direktori proyek atau file .dsx: {args.path}", file=sys.stderr)
        return 2
    project_dir, dsx_name = resolved
    try:
        if args.command == "check":
            result = generate_from_directory(project_dir, None, dsx_name=dsx_name, check_only=True)
        else:
            fmt = args.format
            if args.output and Path(args.output).suffix.lower() in _EXT_FMT:
                fmt = _EXT_FMT[Path(args.output).suffix.lower()]
            output = _fix_output(args.output, fmt, project_dir, Path(dsx_name).stem)
            args.format = fmt
            result = generate_from_directory(
                project_dir, output, args.format, dsx_name=dsx_name, overwrite=not args.no_overwrite
            )
    except KeyboardInterrupt:
        print("Dibatalkan.", file=sys.stderr)
        return 130
    _report(result, args.json)
    if not result.ok:
        return 1
    if not args.json:
        print(f"OK: {result.output_file}" if args.command == "build" else "OK: dokumen valid")
    return 0


def _cmd_form(args: argparse.Namespace) -> int:
    """Subperintah: form default|validate|generate|ui-schema."""
    from .form.generator import generate_project
    from .form.models import default_form, form_ui_schema, load_form
    from .form.validate import validate_form

    if args.form_cmd == "default":
        data = default_form(args.kind)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"OK: form default ({args.kind}) → {args.output}")
        else:
            print(text, end="")
        return 0

    if args.form_cmd == "ui-schema":
        data = form_ui_schema(args.kind)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"OK: ui-schema → {args.output}")
        else:
            print(text, end="")
        return 0

    if args.form_cmd == "validate":
        try:
            data = load_form(args.form)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        issues = validate_form(data)
        if args.json:
            print(json.dumps({"ok": not any(i["level"] == "error" for i in issues), "issues": issues}, ensure_ascii=False, indent=2))
        else:
            if not issues:
                print("OK: form valid")
            for i in issues:
                print(f"{i['level'].upper()}: [{i['path']}] {i['message']}")
        return 1 if any(i["level"] == "error" for i in issues) else 0

    if args.form_cmd == "generate":
        out_dir = Path(args.dir)
        fmt = args.format
        build_target = None
        dsx_name = args.output or "document.dsx"
        # -o hasil.docx/.pdf/.html berarti path DOKUMEN keluaran, bukan nama file .dsx
        if Path(dsx_name).suffix.lower() in _EXT_FMT:
            build_target = dsx_name
            fmt = _EXT_FMT[Path(dsx_name).suffix.lower()]
            dsx_name = "document.dsx"
            args.build = True
        elif not dsx_name.endswith(".dsx"):
            dsx_name += ".dsx"
        try:
            result = generate_project(args.form, out_dir=out_dir, dsx_name=dsx_name)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for i in result.get("issues") or []:
                print(f"{i['level'].upper()}: [{i['path']}] {i['message']}", file=sys.stderr)
            if not result["ok"]:
                print("ERROR: generate gagal (lihat issue di atas)", file=sys.stderr)
                return 1
            print(f"OK: {result['dsx_path']}")
            if result.get("form_path"):
                print(f"OK: {result['form_path']}")
        if not result["ok"]:
            return 1
        if args.build:
            build_out = _fix_output(build_target, fmt, out_dir / Path(dsx_name).parent, Path(dsx_name).stem)
            gen = generate_from_directory(
                out_dir, build_out, fmt, dsx_name=dsx_name, overwrite=True
            )
            _report(gen, args.json)
            if not gen.ok:
                return 1
            if not args.json:
                print(f"OK: {Path(gen.output_file).resolve()}")
        return 0

    if args.form_cmd == "blocks":
        from .form.blocks import list_block_types
        data = list_block_types()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for b in data:
                print(f"{b['type']:18} [{b['group']}] {b['label']}")
        return 0

    if args.form_cmd == "preset":
        from .form.blocks import form_from_preset
        data = form_from_preset(args.name)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"OK: preset {args.name} → {args.output}")
        else:
            print(text, end="")
        return 0

    if args.form_cmd == "convert":
        from .form.blocks import surat_as_blocks
        from .form.models import load_form
        src = load_form(args.form)
        if str(src.get("kind")) != "surat-resmi":
            print("ERROR: convert saat ini hanya dari kind=surat-resmi", file=sys.stderr)
            return 2
        data = surat_as_blocks(src)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        out = args.output or "form-custom.json"
        Path(out).write_text(text, encoding="utf-8")
        print(f"OK: {out} ({len(data.get('blocks') or [])} blok)")
        return 0

    if args.form_cmd == "user-preset":
        from .form import user_presets as up
        if args.up_cmd == "save":
            data = json.loads(Path(args.form).read_text(encoding="utf-8"))
            try:
                result = up.save_user_preset(
                    args.dir, args.name, data,
                    description=args.desc,
                    overwrite=not args.no_overwrite,
                )
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            print(f"OK: preset disimpan → {result['path']}")
            return 0
        if args.up_cmd == "list":
            items = up.list_user_presets(args.dir)
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                if not items:
                    print("(kosong)")
                for it in items:
                    desc = f" — {it['description']}" if it.get("description") else ""
                    print(f"{it['name']:24} kind={it.get('kind')} blocks={it.get('blocks')}{desc}")
            return 0
        if args.up_cmd == "load":
            try:
                data = up.load_user_preset(args.dir, args.name)
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
                print(f"OK: {args.output}")
            else:
                print(text, end="")
            return 0
        if args.up_cmd == "delete":
            try:
                up.delete_user_preset(args.dir, args.name)
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            print(f"OK: preset dihapus: {args.name}")
            return 0
        return 2

    if args.form_cmd == "format":
        from .form.format_dsx import format_dsx
        src_path = Path(args.dsx)
        text = format_dsx(src_path.read_text(encoding="utf-8"))
        if args.stdout:
            print(text, end="")
        else:
            out = Path(args.output) if args.output else src_path
            out.write_text(text, encoding="utf-8")
            print(f"OK: formatted → {out}")
        return 0

    if args.form_cmd == "dsx-to-form":
        from .form.dsx_to_form import dsx_to_form
        src = Path(args.dsx).read_text(encoding="utf-8")
        data = dsx_to_form(src)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"OK: {args.output} ({len(data.get('blocks') or [])} blok)")
        elif args.json:
            print(text, end="")
        else:
            print(f"OK: {len(data.get('blocks') or [])} blok dikenali")
            for i, b in enumerate(data.get("blocks") or []):
                print(f"  [{i}] {b.get('type')}")
            if not args.output:
                print("(pakai -o form.json untuk menulis file)")
        return 0

    if args.form_cmd == "completions":
        from .form.completions import build_completions
        payload = build_completions()
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"OK: completions → {args.output}")
        else:
            print(text, end="")
        return 0

    if args.form_cmd == "serve":
        from .form.server import run_server
        run_server(project_dir=args.dir, host=args.host, port=args.port, form_ui_dir=args.ui)
        return 0

    print("ERROR: subperintah form tidak dikenal", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
