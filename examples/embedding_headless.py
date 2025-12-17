#!/usr/bin/env python3
"""
Example: Headless Command Execution
Shows how to use CmdorcController without any UI for programmatic control.

This example demonstrates:
- Using CmdorcController without CmdorcView
- Programmatic command execution
- Event-based monitoring
- Integration with non-Textual applications
"""

import asyncio

try:
    from textual_cmdorc import CmdorcController
except ImportError:
    print("Error: Install textual-cmdorc first: pip install textual-cmdorc")
    exit(1)


class PipelineExecutor:
    """
    Execute a command pipeline programmatically.

    Use case: CI/CD systems, automated deployments, scheduled tasks.
    """

    def __init__(self, config_path: str):
        """Initialize executor with a config."""
        self.config_path = config_path
        self.controller = CmdorcController(config_path, enable_watchers=False)
        self.results = {}
        self.running_commands = set()

    async def setup(self):
        """Attach controller to event loop."""
        loop = asyncio.get_running_loop()
        self.controller.attach(loop)

        # Wire event handlers
        self.controller.on_command_started = self._on_started
        self.controller.on_command_finished = self._on_finished

        # Check validation
        validation = self.controller.validate_config()
        if validation.errors:
            print(f"❌ Config errors: {validation.errors}")
            return False

        if validation.warnings:
            print(f"⚠️ Warnings: {validation.warnings}")

        print(f"✓ Loaded {validation.commands_loaded} commands")
        return True

    async def execute_command(self, name: str, timeout: float = 60) -> bool:
        """
        Execute a single command and wait for completion.

        Args:
            name: Command name
            timeout: Max seconds to wait

        Returns:
            True if successful, False otherwise
        """
        print(f"\n▶ Executing: {name}")

        # Request run
        self.controller.request_run(name)

        # Wait for completion with timeout
        start = asyncio.get_event_loop().time()
        while name in self.running_commands:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                print(f"❌ Timeout waiting for {name}")
                return False

            await asyncio.sleep(0.1)

        result = self.results.get(name)
        if result:
            success = result.get("success", False)
            print(f"{'✓' if success else '✗'} {name} → {result.get('state', 'unknown')}")
            return success

        return False

    async def execute_workflow(self, *command_names, parallel: bool = False) -> dict:
        """
        Execute a sequence of commands.

        Args:
            *command_names: Names of commands to execute
            parallel: If True, execute all at once; if False, sequential

        Returns:
            Dict mapping command names to results
        """
        if parallel:
            # Execute all commands concurrently
            print(f"\n▶ Executing {len(command_names)} commands in parallel...")
            tasks = [self.execute_command(name) for name in command_names]
            await asyncio.gather(*tasks)
        else:
            # Execute sequentially
            print(f"\n▶ Executing {len(command_names)} commands sequentially...")
            for name in command_names:
                success = await self.execute_command(name)
                if not success:
                    print(f"⚠️ {name} failed, continuing anyway...")

        return self.results

    async def teardown(self):
        """Cleanup controller."""
        self.controller.detach()

    def _on_started(self, name: str, trigger):
        """Handler for command start."""
        self.running_commands.add(name)

    def _on_finished(self, name: str, result):
        """Handler for command completion."""
        self.running_commands.discard(name)
        self.results[name] = {
            "state": result.state.value,
            "success": result.state.value == "success",
            "duration": getattr(result, "duration_str", "?"),
        }


async def example_ci_pipeline():
    """Example: CI pipeline execution."""
    print("=" * 60)
    print("Example 1: CI Pipeline Execution")
    print("=" * 60)

    executor = PipelineExecutor("config.toml")

    if not await executor.setup():
        return

    # Run CI pipeline: Lint → Format → Test
    await executor.execute_workflow("Lint", "Format", "Test", parallel=False)

    print("\n📊 Results:")
    for cmd, result in executor.results.items():
        print(f"  {cmd}: {result['state']} ({result['duration']})")

    await executor.teardown()


async def example_deployment():
    """Example: Production deployment with safety checks."""
    print("\n" + "=" * 60)
    print("Example 2: Production Deployment")
    print("=" * 60)

    executor = PipelineExecutor("config.toml")

    if not await executor.setup():
        return

    # Deployment pipeline: Build → Test → Deploy
    pipeline = ["Build", "Test", "Deploy"]

    # Ask for confirmation
    print("\nDeployment checklist:")
    print("  ☐ Tests passing")
    print("  ☐ Version bumped")
    print("  ☐ Changelog updated")

    # Run with safety: abort on any failure
    for cmd in pipeline:
        success = await executor.execute_command(cmd)
        if not success:
            print(f"\n❌ {cmd} failed! Aborting deployment.")
            break
    else:
        print("\n✓ Deployment completed successfully!")

    await executor.teardown()


async def example_monitoring():
    """Example: Continuous monitoring task."""
    print("\n" + "=" * 60)
    print("Example 3: Health Check Monitoring")
    print("=" * 60)

    executor = PipelineExecutor("config.toml")

    if not await executor.setup():
        return

    # Run health check periodically
    print("\n▶ Running health checks (3 iterations)...")
    for iteration in range(1, 4):
        print(f"\n--- Check {iteration} ---")
        await executor.execute_command("HealthCheck", timeout=30)
        if iteration < 3:
            print("⏳ Waiting 5 seconds...")
            await asyncio.sleep(5)

    print("\n📊 Health check history:")
    for _cmd, result in executor.results.items():
        print(f"  {result['state']}: {result['duration']}")

    await executor.teardown()


async def main():
    """Run all examples."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  textual-cmdorc Headless Execution Examples              ║")
    print("╚════════════════════════════════════════════════════════════╝")

    try:
        # Example 1: Basic CI pipeline
        await example_ci_pipeline()

        # Example 2: Deployment with checks
        # await example_deployment()

        # Example 3: Monitoring
        # await example_monitoring()

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
