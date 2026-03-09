import click


@click.group()
def cli():
    """SKM - Skill Manager for AI coding agents."""
    pass


@cli.command()
def install():
    """Install/remove skills based on config."""
    click.echo("install: not yet implemented")


@cli.command()
def check_updates():
    """Check for skill updates."""
    click.echo("check-updates: not yet implemented")


@cli.command()
@click.argument("skill_name")
def update(skill_name: str):
    """Update a specific skill."""
    click.echo(f"update {skill_name}: not yet implemented")


@cli.command(name="list")
def list_skills():
    """List installed skills and their linked paths."""
    click.echo("list: not yet implemented")
