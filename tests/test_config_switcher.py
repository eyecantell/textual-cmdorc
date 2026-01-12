"""Tests for ConfigSwitcher widget."""

from textual_cmdorc.config_switcher import ConfigSwitcher


class TestConfigSwitcherInitialization:
    """Tests for ConfigSwitcher initialization."""

    def test_basic_init(self):
        """ConfigSwitcher initializes with config names and active name."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod", "Test"],
            active_name="Dev",
        )
        assert switcher.active_name == "Dev"
        assert switcher.config_names == ["Dev", "Prod", "Test"]

    def test_single_config(self):
        """ConfigSwitcher works with single config."""
        switcher = ConfigSwitcher(
            config_names=["Only"],
            active_name="Only",
        )
        assert switcher.active_name == "Only"
        assert len(switcher.config_names) == 1

    def test_config_names_is_copy(self):
        """config_names property returns a copy, not the original list."""
        original = ["A", "B"]
        switcher = ConfigSwitcher(config_names=original, active_name="A")
        returned = switcher.config_names
        returned.append("C")
        assert "C" not in switcher.config_names


class TestConfigSwitcherDisplay:
    """Tests for ConfigSwitcher display behavior."""

    def test_update_display_called_on_init(self):
        """_update_display is called during initialization."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        # Verify the internal state was set up
        assert switcher._active_name == "Dev"
        assert not switcher._dropdown_open

    def test_dropdown_open_changes_display_mode(self):
        """Opening dropdown changes display behavior."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        # Initially closed
        assert not switcher._dropdown_open

        # Open dropdown
        switcher._dropdown_open = True
        switcher._update_display()
        # State should be maintained
        assert switcher._dropdown_open


class TestConfigSwitcherSelection:
    """Tests for ConfigSwitcher selection behavior."""

    def test_select_config_changes_active(self):
        """select_config changes the active config."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod", "Test"],
            active_name="Dev",
        )
        switcher.select_config("Prod")
        assert switcher.active_name == "Prod"

    def test_select_config_posts_message(self):
        """select_config posts ConfigSelected message."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.select_config("Prod")

        assert len(messages) == 1
        assert isinstance(messages[0], ConfigSwitcher.ConfigSelected)
        assert messages[0].config_name == "Prod"

    def test_select_same_config_no_message(self):
        """Selecting the already-active config doesn't post message."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.select_config("Dev")

        assert len(messages) == 0

    def test_select_invalid_config_ignored(self):
        """Selecting non-existent config is ignored."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.select_config("NonExistent")

        assert switcher.active_name == "Dev"
        assert len(messages) == 0


class TestConfigSwitcherSetActiveSilently:
    """Tests for set_active_silently method."""

    def test_set_active_silently_changes_config(self):
        """set_active_silently changes the active config."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        switcher.set_active_silently("Prod")
        assert switcher.active_name == "Prod"

    def test_set_active_silently_no_message(self):
        """set_active_silently doesn't post a message."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.set_active_silently("Prod")

        assert len(messages) == 0

    def test_set_active_silently_invalid_ignored(self):
        """set_active_silently with invalid name is ignored."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )
        switcher.set_active_silently("NonExistent")
        assert switcher.active_name == "Dev"


class TestConfigSwitcherCycle:
    """Tests for cycle_next and cycle_prev methods."""

    def test_cycle_next(self):
        """cycle_next moves to next config."""
        switcher = ConfigSwitcher(
            config_names=["A", "B", "C"],
            active_name="A",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.cycle_next()
        assert switcher.active_name == "B"
        assert len(messages) == 1
        assert messages[0].config_name == "B"

    def test_cycle_next_wraps(self):
        """cycle_next wraps from last to first."""
        switcher = ConfigSwitcher(
            config_names=["A", "B", "C"],
            active_name="C",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.cycle_next()
        assert switcher.active_name == "A"

    def test_cycle_prev(self):
        """cycle_prev moves to previous config."""
        switcher = ConfigSwitcher(
            config_names=["A", "B", "C"],
            active_name="B",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.cycle_prev()
        assert switcher.active_name == "A"
        assert len(messages) == 1

    def test_cycle_prev_wraps(self):
        """cycle_prev wraps from first to last."""
        switcher = ConfigSwitcher(
            config_names=["A", "B", "C"],
            active_name="A",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.cycle_prev()
        assert switcher.active_name == "C"

    def test_cycle_single_config_noop(self):
        """cycle_next/prev with single config does nothing."""
        switcher = ConfigSwitcher(
            config_names=["Only"],
            active_name="Only",
        )
        messages = []
        switcher.post_message = lambda msg: messages.append(msg)

        switcher.cycle_next()
        assert switcher.active_name == "Only"
        assert len(messages) == 0

        switcher.cycle_prev()
        assert switcher.active_name == "Only"
        assert len(messages) == 0


class TestConfigSwitcherDropdown:
    """Tests for dropdown toggle behavior."""

    def test_click_toggles_dropdown(self):
        """Clicking toggles dropdown state."""
        switcher = ConfigSwitcher(
            config_names=["Dev", "Prod"],
            active_name="Dev",
        )

        # Initially closed
        assert not switcher._dropdown_open

        # Click opens
        switcher.on_click()
        assert switcher._dropdown_open

        # Click closes
        switcher.on_click()
        assert not switcher._dropdown_open
