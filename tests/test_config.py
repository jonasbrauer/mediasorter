from mediasorter.config import read_config


def test_sample_config(sample_config_path):
    assert read_config(sample_config_path)
