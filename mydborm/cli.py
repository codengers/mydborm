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

cli     = typer.Typer(
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
#  Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    cli()





