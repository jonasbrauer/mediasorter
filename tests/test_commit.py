import os
import random
import shutil
from tempfile import TemporaryDirectory

import pytest

from mediasorter.config import ScanConfig, OperationOptions
from mediasorter.runner import Action
from mediasorter.sorter import MediaSorter, MediaType


@pytest.fixture
def tmp_tv_show(shows, shows_dir):
    show = os.path.join(shows_dir, random.choice(shows))
    with TemporaryDirectory() as tmp_src_dir:
        src_result = os.path.join(tmp_src_dir, os.path.basename(show))
        shutil.copy(show, src_result)
        assert os.path.exists(src_result)
        yield src_result


@pytest.fixture
def tmp_movie(movies, movies_dir):
    movie = os.path.join(movies_dir, random.choice(movies))
    with TemporaryDirectory() as tmp_src_dir:
        src_result = os.path.join(tmp_src_dir, os.path.basename(movie))
        shutil.copy(movie, src_result)
        assert os.path.exists(src_result)
        yield src_result


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [a for a in Action])
async def test_operation_commit(test_config, tmp_tv_show, action):

    with TemporaryDirectory() as tmp_dir:
        sorter = MediaSorter.from_src_path(
            test_config,
            src_path=tmp_tv_show,
            media_type=MediaType.TV_SHOW,
            action=action,
            tv_shows_output=tmp_dir,
            movies_output=tmp_dir
        )

        ops = await sorter.scan_all()
        assert len(ops) == 1
        op = ops[0]
        assert op.raise_error()

        assert not os.path.exists(op.output_path)
        await sorter.commit_all(ops)

        assert op.raise_error()
        assert os.path.exists(op.output_path)
        if action == Action.MOVE:
            assert not os.path.exists(tmp_tv_show), f"{action} original file wasn't deleted"
        else:
            assert os.path.exists(tmp_tv_show), f"{action} original file was deleted"


@pytest.mark.asyncio
async def test_operation_commit_meta_files(test_config, tmp_tv_show):
    with TemporaryDirectory() as tmp_dir:
        sorter = MediaSorter.from_src_path(
            test_config,
            src_path=tmp_tv_show,
            media_type=MediaType.TV_SHOW,
            action=Action.COPY,
            tv_shows_output=tmp_dir,
            movies_output=tmp_dir,
            options=OperationOptions(infofile=True, shasum=True)
        )
        expected_path = os.path.join(tmp_dir, *await sorter.suggest_tv_show(tmp_tv_show))
        original_ext = os.path.splitext(tmp_tv_show)[-1]
        await sorter.commit_all(await sorter.scan_all())

        expected_files = [
            expected_path + original_ext + ext for ext in ('', ".sha256sum", ".txt")
        ]
        for path in expected_files:
            list_dir = os.listdir(tmp_dir)
            assert os.path.exists(path), f"\"{path}\" NOT FOUND, actual files: {list_dir}"



@pytest.mark.asyncio
async def test_operation_commit_meta_files_MOV(real_config, tmp_movie):
    with TemporaryDirectory() as tmp_dir:
        sorter = MediaSorter.from_src_path(
            real_config,
            src_path=tmp_movie,
            media_type=MediaType.MOVIE,
            action=Action.COPY,
            tv_shows_output=tmp_dir,
            movies_output=tmp_dir,
            options=OperationOptions(infofile=True, shasum=True)
        )
        expected_path = os.path.join(tmp_dir, *await sorter.suggest_movie(tmp_movie))
        original_ext = os.path.splitext(tmp_movie)[-1]
        await sorter.commit_all(await sorter.scan_all())

        expected_files = [
            expected_path + original_ext + ext for ext in ('', ".sha256sum", ".txt")
        ]
        for path in expected_files:
            list_dir = os.listdir(tmp_dir)
            assert os.path.exists(path), f"\"{path}\" NOT FOUND, actual files: {list_dir}"


