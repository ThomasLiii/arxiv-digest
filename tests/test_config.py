from pathlib import Path

import pytest

from arxiv_digest import config

REPO = Path(__file__).parent.parent


def write(tmp_path, toml, interests="## High priority\n- lensing\n"):
    (tmp_path / "interests.md").write_text(interests)
    path = tmp_path / "digest.toml"
    path.write_text(toml)
    return path


def test_repo_config_loads():
    cfg = config.load(REPO / "digest.toml")
    assert cfg.categories
    assert cfg.output_dir == REPO / "digests"
    assert "<!--" not in cfg.interests
    assert cfg.interests.startswith("# Research interests")


def test_defaults(tmp_path):
    cfg = config.load(write(tmp_path, 'categories = ["astro-ph.CO", "astro-ph.CO"]'))
    assert cfg.categories == ["astro-ph.CO"]
    assert cfg.batch_size == 40
    assert cfg.include_cross_lists and not cfg.include_replacements
    assert cfg.output_dir == tmp_path / "digests"


@pytest.mark.parametrize(
    "toml, message",
    [
        ('categorys = ["astro-ph.CO"]', "unknown setting 'categorys'"),
        ("categories = []", "at least one arXiv category"),
        ('categories = "astro-ph.CO"', "'categories' should be a list"),
        ('categories = ["astro-ph.CO"]\nbatch_size = true', "'batch_size' should be a whole number"),
        ('categories = ["astro-ph.CO"]\ninclude_cross_lists = "yes"', "should be true or false"),
        ('categories = ["astro-ph.CO"]\nbatch_size = 0', "at least 1"),
        ('categories = ["astro-ph.CO"]\n[scoring]\nmodel = "x"', "unknown setting 'scoring.model'"),
        ('categories = ["astro-ph.CO"]\ninterests_file = "nope.md"', "nope.md not found"),
        ("categories = [", "digest.toml"),
    ],
)
def test_mistakes_are_explained(tmp_path, toml, message):
    with pytest.raises(config.ConfigError, match=message):
        config.load(write(tmp_path, toml))


def test_empty_interests(tmp_path):
    with pytest.raises(config.ConfigError, match="is empty"):
        config.load(write(tmp_path, 'categories = ["astro-ph.CO"]', interests="<!-- only a comment -->\n"))


def test_missing_config(tmp_path):
    with pytest.raises(config.ConfigError, match="not found"):
        config.load(tmp_path / "digest.toml")
