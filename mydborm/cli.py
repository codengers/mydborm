# =============================================================================
# File        : cli.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Command-line interface built with Typer. Provides
#               terminal commands: mydborm version, mydborm inspect,
#               mydborm shell, mydborm ping.
#               Install: pip install mydborm[cli]
# =============================================================================

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

cli = typer.Typer(
    name="mydborm",
    help="mydborm — Lightweight ORM for MySQL and YugabyteDB",
    add_completion=False,
)
console = Console()


# ------------------------------------------------------------------ #
#  version                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def version():
    """Show mydborm version and supported databases."""
    from mydborm import __version__, __author__
    console.print(Panel(
        f"[bold cyan]mydborm[/bold cyan] v{__version__}\n"
        f"[dim]Author  : {__author__}[/dim]\n"
        f"[dim]License : MIT[/dim]\n"
        f"[dim]Supports: MySQL 8+ | YugabyteDB (YSQL)[/dim]",
        title="[bold green]mydborm CLI[/bold green]",
        border_style="green",
    ))


# ------------------------------------------------------------------ #
#  ping                                                                #
# ------------------------------------------------------------------ #

@cli.command()
def ping(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d", help="mysql or yugabyte"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h", help="Database host"),
    port:     int = typer.Option(3306,        "--port",     "-p", help="Database port"),
    user:     str = typer.Option("root",      "--user",     "-u", help="Database user"),
    password: str = typer.Option("",          "--password", "-w", help="Database password", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n", help="Database name"),
):
    """Test database connectivity and show server info."""
    from mydborm.db import db

    console.print(f"\n[cyan]Connecting to[/cyan] [bold]{dialect}[/bold] "
                  f"at [bold]{host}:{port}[/bold] ...")

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            if dialect == "mysql":
                cur.execute("SELECT VERSION(), DATABASE(), USER()")
                row = cur.fetchone()
                t = Table(box=box.ROUNDED, border_style="green")
                t.add_column("Property", style="cyan")
                t.add_column("Value",    style="white")
                t.add_row("Status",   "[bold green]✔ Connected[/bold green]")
                t.add_row("Dialect",  dialect)
                t.add_row("Version",  row[0])
                t.add_row("Database", row[1])
                t.add_row("User",     row[2])
            else:
                cur.execute("SELECT VERSION(), current_database(), current_user")
                row = cur.fetchone()
                t = Table(box=box.ROUNDED, border_style="green")
                t.add_column("Property", style="cyan")
                t.add_column("Value",    style="white")
                t.add_row("Status",   "[bold green]✔ Connected[/bold green]")
                t.add_row("Dialect",  dialect)
                t.add_row("Version",  row[0])
                t.add_row("Database", row[1])
                t.add_row("User",     row[2])

            console.print(t)
        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Connection failed:[/bold red] {e}\n")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  inspect                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def inspect(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h"),
    port:     int = typer.Option(3306,        "--port",     "-p"),
    user:     str = typer.Option("root",      "--user",     "-u"),
    password: str = typer.Option("",          "--password", "-w", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n"),
):
    """Inspect all tables and columns in the connected database."""
    from mydborm.db import db

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            # Get all tables
            if dialect == "mysql":
                cur.execute("SHOW TABLES;")
                tables = [row[0] for row in cur.fetchall()]
            else:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]

            if not tables:
                console.print(
                    f"\n[yellow]No tables found in database "
                    f"'{database}'.[/yellow]\n"
                )
                return

            console.print(
                f"\n[bold cyan]Database:[/bold cyan] {database}  "
                f"[bold cyan]Dialect:[/bold cyan] {dialect}  "
                f"[bold cyan]Tables:[/bold cyan] {len(tables)}\n"
            )

            for table in tables:
                # Get columns
                if dialect == "mysql":
                    cur.execute(f"DESCRIBE `{table}`;")
                    rows = cur.fetchall()
                    t = Table(
                        title=f"[bold]{table}[/bold]",
                        box=box.SIMPLE_HEAVY,
                        border_style="cyan",
                        show_lines=True,
                    )
                    t.add_column("Column",  style="bold white")
                    t.add_column("Type",    style="yellow")
                    t.add_column("Null",    style="dim")
                    t.add_column("Key",     style="green")
                    t.add_column("Default", style="dim")
                    for row in rows:
                        t.add_row(
                            str(row[0]), str(row[1]),
                            str(row[2]), str(row[3]),
                            str(row[4]) if row[4] else "-"
                        )
                else:
                    cur.execute(f"""
                        SELECT column_name, data_type, is_nullable,
                               column_default
                        FROM information_schema.columns
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position;
                    """)
                    rows = cur.fetchall()
                    t = Table(
                        title=f"[bold]{table}[/bold]",
                        box=box.SIMPLE_HEAVY,
                        border_style="cyan",
                        show_lines=True,
                    )
                    t.add_column("Column",   style="bold white")
                    t.add_column("Type",     style="yellow")
                    t.add_column("Nullable", style="dim")
                    t.add_column("Default",  style="dim")
                    for row in rows:
                        t.add_row(
                            str(row[0]), str(row[1]),
                            str(row[2]),
                            str(row[3]) if row[3] else "-"
                        )

                console.print(t)

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  tables                                                              #
# ------------------------------------------------------------------ #

@cli.command()
def tables(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h"),
    port:     int = typer.Option(3306,        "--port",     "-p"),
    user:     str = typer.Option("root",      "--user",     "-u"),
    password: str = typer.Option("",          "--password", "-w", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n"),
):
    """List all tables in the connected database."""
    from mydborm.db import db

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            if dialect == "mysql":
                cur.execute("SHOW TABLES;")
            else:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)

            rows = cur.fetchall()

            t = Table(
                title=f"Tables in [bold]{database}[/bold]",
                box=box.ROUNDED,
                border_style="cyan",
            )
            t.add_column("#",     style="dim", width=4)
            t.add_column("Table", style="bold white")

            for i, row in enumerate(rows, 1):
                t.add_row(str(i), row[0])

            console.print()
            console.print(t)
            console.print(
                f"\n[dim]{len(rows)} table(s) found.[/dim]\n"
            )

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)

# ------------------------------------------------------------------ #
#  migrate                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def migrate(
    dialect:     str  = typer.Option("mysql",     "--dialect",  "-d"),
    host:        str  = typer.Option("127.0.0.1", "--host",     "-h"),
    port:        int  = typer.Option(3306,        "--port",     "-p"),
    user:        str  = typer.Option("root",      "--user",     "-u"),
    password:    str  = typer.Option("",          "--password", "-w", hide_input=True),
    database:    str  = typer.Option("testdb",    "--database", "-n"),
    status:      bool = typer.Option(False,       "--status",   "-s", help="Show migration history"),
    rollback:    bool = typer.Option(False,       "--rollback", "-r", help="Rollback last migration"),
    model_path:  str  = typer.Option("",          "--model",    "-m", help="Python import path to model e.g. myapp.models.User"),
):
    """
    Run, inspect, or rollback migrations.

    Examples:
        mydborm migrate --status
        mydborm migrate --model myapp.models.User
        mydborm migrate --rollback --model myapp.models.User
    """
    from mydborm.db import db
    import mydborm.migrations as mg

    # Configure DB
    db.configure(
        dialect=dialect, host=host, port=port,
        user=user, password=password, database=database
    )

    # ── Status ────────────────────────────────────────────────────── #
    if status:
        records = mg.migration_status()
        if not records:
            console.print("\n[yellow]No migrations applied yet.[/yellow]\n")
            return

        t = Table(
            title="Migration History",
            box=box.ROUNDED,
            border_style="cyan",
            show_lines=True,
        )
        t.add_column("ID",          style="dim",        width=4)
        t.add_column("Version",     style="cyan",       width=18)
        t.add_column("Description", style="white")
        t.add_column("Applied At",  style="green",      width=20)
        t.add_column("Status",      style="bold",       width=12)

        for r in records:
            status_str = (
                "[red]Rolled Back[/red]"
                if r["rolled_back"]
                else "[green]Applied[/green]"
            )
            t.add_row(
                str(r["id"]),
                r["version"],
                r["description"],
                str(r["applied_at"]),
                status_str,
            )

        console.print()
        console.print(t)
        console.print(f"\n[dim]{len(records)} migration(s) found.[/dim]\n")
        return

    # ── Rollback / Apply — need a model ───────────────────────────── #
    if not model_path:
        console.print(
            "\n[yellow]Tip:[/yellow] Use --status to see migration history.\n"
            "     Use --model <import.path.ModelName> to migrate a model.\n"
        )
        return

    # Dynamically import the model class
    try:
        parts      = model_path.rsplit(".", 1)
        module     = __import__(parts[0], fromlist=[parts[1]])
        model_cls  = getattr(module, parts[1])
    except Exception as e:
        console.print(f"\n[red]✘ Could not import model:[/red] {e}\n")
        raise typer.Exit(code=1)

    # ── Rollback ──────────────────────────────────────────────────── #
    if rollback:
        console.print(
            f"\n[yellow]Rolling back[/yellow] "
            f"[bold]{model_cls._table}[/bold] ..."
        )
        result = mg.rollback(model_cls)
        if result["applied"]:
            console.print(f"[green]✔[/green] {result['message']}\n")
        else:
            console.print(f"[yellow]⚠[/yellow]  {result['message']}\n")
        return

    # ── Apply migration ───────────────────────────────────────────── #
    console.print(
        f"\n[cyan]Inspecting[/cyan] "
        f"[bold]{model_cls._table}[/bold] ..."
    )

    # Show diff first
    diff = mg.diff_schema(model_cls)

    if not diff["new_table"] and not diff["add_columns"] and not diff["drop_columns"]:
        console.print(
            f"[green]✔[/green] Table [bold]{diff['table']}[/bold] "
            f"is already up to date.\n"
        )
        return

    # Show what will change
    t = Table(
        title=f"Planned changes for [bold]{diff['table']}[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="yellow",
    )
    t.add_column("Action",  style="bold", width=12)
    t.add_column("Column",  style="white")
    t.add_column("Details", style="dim")

    if diff["new_table"]:
        t.add_row("[green]CREATE[/green]", diff["table"], "New table")

    for col, defn in diff["add_columns"].items():
        t.add_row("[green]ADD[/green]", col, defn)

    for col in diff["drop_columns"]:
        t.add_row("[red]DROP[/red]", col, "Column removed from model")

    console.print()
    console.print(t)

    # Apply
    result = mg.migrate(model_cls)
    console.print()
    if result["applied"]:
        for sql in result["sqls"]:
            console.print(f"[dim]  ▶ {sql}[/dim]")
        console.print(
            f"\n[green]✔[/green] {result['message']}\n"
        )
    else:
        console.print(
            f"[yellow]⚠[/yellow]  {result['message']}\n"
        )

# ------------------------------------------------------------------ #
#  pool                                                                #
# ------------------------------------------------------------------ #

@cli.command()
def pool(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h"),
    port:     int = typer.Option(3306,        "--port",     "-p"),
    user:     str = typer.Option("root",      "--user",     "-u"),
    password: str = typer.Option("",          "--password", "-w",
                                 hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n"),
    size:     int = typer.Option(5,           "--size",     "-s",
                                 help="Pool size"),
    overflow: int = typer.Option(10,          "--overflow",
                                 help="Max overflow connections"),
):
    """Show connection pool status and configuration."""
    from mydborm.db import db

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        db.configure_pool(pool_size=size, max_overflow=overflow)

        status = db.pool_status()
        alive  = db.ping()

        t = Table(
            title="Connection Pool Status",
            box=box.ROUNDED,
            border_style="cyan",
        )
        t.add_column("Property", style="cyan")
        t.add_column("Value",    style="white")

        t.add_row("Dialect",      status["dialect"])
        t.add_row("Host",         str(status["host"]))
        t.add_row("Database",     str(status["database"]))
        t.add_row("Pool size",    str(size))
        t.add_row("Max overflow", str(overflow))
        t.add_row(
            "Status",
            "[bold green]✔ Alive[/bold green]"
            if alive else
            "[bold red]✘ Unreachable[/bold red]"
        )

        console.print()
        console.print(t)
        console.print()

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)

# ------------------------------------------------------------------ #
#  generate                                                            #
# ------------------------------------------------------------------ #

@cli.command()
def generate(
    dialect:    str = typer.Option("mysql",        "--dialect",   "-d"),
    host:       str = typer.Option("127.0.0.1",    "--host",      "-h"),
    port:       int = typer.Option(3306,           "--port",      "-p"),
    user:       str = typer.Option("root",         "--user",      "-u"),
    password:   str = typer.Option("",             "--password",  "-w", hide_input=True),
    database:   str = typer.Option("testdb",       "--database",  "-n"),
    model:      str = typer.Option("",             "--model",     "-m",
                                   help="Dotted model path e.g. myapp.models.User"),
    output_dir: str = typer.Option("migrations",   "--output",    "-o",
                                   help="Output directory for SQL files"),
    apply:      bool = typer.Option(False,         "--apply",     "-a",
                                    help="Apply migration after generating"),
    list_files: bool = typer.Option(False,         "--list",      "-l",
                                    help="List existing migration files"),
):
    """Generate versioned SQL migration files from model diff."""
    from mydborm.db import db
    from mydborm import migrations as mg

    db.configure(
        dialect=dialect, host=host, port=port,
        user=user, password=password, database=database
    )

    if list_files:
        files = mg.list_migration_files(output_dir)
        if not files:
            console.print(f"\n[dim]No migration files found in '{output_dir}'[/dim]\n")
            return
        t = Table(
            title=f"Migration files in '{output_dir}'",
            box=box.ROUNDED, border_style="cyan"
        )
        t.add_column("Version", style="cyan")
        t.add_column("Name",    style="white")
        t.add_column("File",    style="dim")
        for f in files:
            t.add_row(f["version"], f["name"], f["filename"])
        console.print()
        console.print(t)
        console.print()
        db.close()
        return

    if not model:
        console.print("\n[bold yellow]Tip:[/bold yellow] "
                      "Use [cyan]--model myapp.models.User[/cyan] to generate a migration.\n"
                      "Use [cyan]--list[/cyan] to see existing migration files.\n")
        db.close()
        return

    try:
        import importlib
        parts      = model.rsplit(".", 1)
        if len(parts) != 2:
            console.print(f"\n[bold red]Error:[/bold red] "
                          f"Invalid model path: {model!r}. "
                          f"Use dotted path e.g. myapp.models.User\n")
            raise typer.Exit(code=1)

        module_path, class_name = parts
        module      = importlib.import_module(module_path)
        model_class = getattr(module, class_name)

        result = mg.generate(
            model_class,
            output_dir  = output_dir,
            description = class_name.lower(),
            apply       = apply,
        )

        if result["file"] is None:
            console.print(
                f"\n[bold green]✔[/bold green] {result['message']}\n"
            )
        else:
            t = Table(
                title="Migration generated",
                box=box.ROUNDED, border_style="cyan"
            )
            t.add_column("Property", style="cyan")
            t.add_column("Value",    style="white")
            t.add_row("File",    result["file"])
            t.add_row("Version", result["version"])
            t.add_row("SQL",     str(len(result["sqls"])) + " statement(s)")
            t.add_row("Applied", "[green]yes[/green]" if result["applied"] else "[dim]no[/dim]")
            console.print()
            console.print(t)
            console.print()

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)

# ------------------------------------------------------------------ #
#  migrate-db                                                          #
# ------------------------------------------------------------------ #

@cli.command("migrate-db")
def migrate_db(
    source_dialect:  str  = typer.Option(...,         "--source-dialect",  help="mysql, yugabyte, or postgres"),
    source_host:     str  = typer.Option("127.0.0.1",  "--source-host"),
    source_port:     int  = typer.Option(3306,         "--source-port"),
    source_user:     str  = typer.Option("root",       "--source-user"),
    source_password: str  = typer.Option(...,          "--source-password", hide_input=True),
    source_db:       str  = typer.Option(...,          "--source-db"),
    target_dialect:  str  = typer.Option(...,          "--target-dialect",  help="mysql, yugabyte, or postgres"),
    target_host:     str  = typer.Option("127.0.0.1",  "--target-host"),
    target_port:     int  = typer.Option(5433,         "--target-port"),
    target_user:     str  = typer.Option("yugabyte",   "--target-user"),
    target_password: str  = typer.Option(...,          "--target-password", hide_input=True),
    target_db:       str  = typer.Option(...,          "--target-db"),
    tables:          str  = typer.Option(None,         "--tables",     help="Comma-separated table names (default: all tables)"),
    chunk_size:      int  = typer.Option(500,          "--chunk-size", help="Rows per INSERT batch"),
    overwrite:       bool = typer.Option(False,        "--overwrite",  help="Replace tables that already have data in the target"),
    dry_run:         bool = typer.Option(False,         "--dry-run",   help="Preview the migration without writing anything"),
):
    """
    Migrate all (or selected) tables from one database to another.

    Examples:
        mydborm migrate-db --source-dialect mysql --source-password root --source-db shop \\
                            --target-dialect yugabyte --target-password yugabyte --target-db shop

        mydborm migrate-db ... --tables users,orders --dry-run
    """
    from mydborm.migrate import MigrationEngine, SchemaExtractor, DataTransfer

    table_list = [t.strip() for t in tables.split(",") if t.strip()] if tables else None

    engine = MigrationEngine(
        source={
            "dialect": source_dialect, "host": source_host, "port": source_port,
            "user": source_user, "password": source_password, "database": source_db,
        },
        target={
            "dialect": target_dialect, "host": target_host, "port": target_port,
            "user": target_user, "password": target_password, "database": target_db,
        },
    )

    if dry_run:
        try:
            preview = engine.dry_run(tables=table_list)
        except Exception as e:
            console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
            raise typer.Exit(code=1)

        if not preview["tables"]:
            console.print("\n[yellow]No tables found to migrate.[/yellow]\n")
            return

        t = Table(
            title=f"Dry run: {source_db} ({source_dialect}) → {target_db} ({target_dialect})",
            box=box.ROUNDED, border_style="cyan",
        )
        t.add_column("Table",   style="bold white")
        t.add_column("Rows",    justify="right", style="yellow")
        t.add_column("Columns", justify="right", style="dim")
        for row in preview["tables"]:
            t.add_row(row["table"], f"{row['rows']:,}", str(row["columns"]))

        console.print()
        console.print(t)
        console.print(
            f"\n[dim]{len(preview['tables'])} table(s), "
            f"{sum(row['rows'] for row in preview['tables']):,} row(s) total.[/dim]"
        )
        if preview["warnings"]:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in preview["warnings"]:
                console.print(f"  [yellow]⚠[/yellow] {w}")
        console.print()
        return

    # Resolve the table list and a best-effort row count for the status
    # table up front. Extraction failures here are per-table and non-fatal
    # — engine.run() below does its own per-table error handling, so a
    # single bad table name shouldn't abort the whole migration.
    try:
        table_names = (
            table_list if table_list is not None
            else SchemaExtractor(engine.source_db).list_tables()
        )
    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)

    if not table_names:
        console.print("\n[yellow]No tables found to migrate.[/yellow]\n")
        return

    transfer   = DataTransfer(engine.source_db, engine.target_db)
    row_totals = {}
    for name in table_names:
        try:
            row_totals[name] = transfer.count_rows(engine.source_db, name)
        except Exception:
            row_totals[name] = 0

    console.print(
        f"\n[cyan]Migrating[/cyan] [bold]{source_db}[/bold] ({source_dialect}) "
        f"[cyan]→[/cyan] [bold]{target_db}[/bold] ({target_dialect})\n"
    )

    def on_progress(table_name, done, total):
        if total and done >= total:
            console.print(f"  [green]✔[/green] {table_name} — {total:,} row(s) transferred")

    try:
        result = engine.run(
            tables=table_list, chunk_size=chunk_size,
            overwrite=overwrite, on_progress=on_progress, verify=True,
        )
    except Exception as e:
        console.print(f"\n[bold red]✘ Migration failed:[/bold red] {e}\n")
        raise typer.Exit(code=1)

    failed_names  = {e.split(":", 1)[0].strip() for e in result.errors}
    skipped_names = {
        w.split("'")[1] for w in result.warnings
        if w.startswith("Skipped '")
    }

    t = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    t.add_column("Table",  style="bold white")
    t.add_column("Rows",   justify="right", style="yellow")
    t.add_column("Status", style="white")

    done_count = 0
    for name in table_names:
        rows = row_totals.get(name, 0)
        if name in failed_names:
            status_text = "[red]✘ Failed[/red]"
        elif name in skipped_names:
            status_text = "[yellow]⚠ Skipped[/yellow]"
        else:
            status_text = "[green]✔ Done[/green]"
            done_count += 1
        t.add_row(name, f"{rows:,}", status_text)

    t.add_row(
        "[bold]Total[/bold]",
        f"[bold]{sum(row_totals.values()):,}[/bold]",
        f"[bold]{done_count}/{len(table_names)} done[/bold]",
    )

    console.print()
    console.print(t)
    console.print()
    console.print(result.summary())
    console.print()

    if not result.is_success():
        raise typer.Exit(code=1)

# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    cli()





