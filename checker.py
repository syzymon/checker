import subprocess
import asyncio
import configparser
from pathlib import Path


def script_directory():
    return Path(__file__).parents[0]


def get_testdata(gen_cmd):  # TODO try to remove shell=True
    proc = subprocess.Popen(gen_cmd, stdout=subprocess.PIPE, shell=True)
    stdout, stderr = proc.communicate()
    return stdout


async def run_and_save(prog_number, prog_cmd, input_test, stdout):
    out_filename = f"prog{prog_number}.{'out' if stdout else 'err'}"

    redirect_out = asyncio.subprocess.PIPE
    redirect_err = asyncio.subprocess.PIPE

    with open(out_filename, "wb+") as out_file:
        if stdout:
            redirect_out = out_file
        else:
            redirect_err = out_file

        proc = await asyncio.create_subprocess_shell(
            prog_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=redirect_out,
            stderr=redirect_err
        )
        proc.stdin.write(input_test)
        proc.stdin.close()
        await proc.wait()
    return out_filename


async def save_outputs(numbered_prog_cmds, input_test, stdout):
    programs = [
        run_and_save(prog_number, prog_cmd, input_test, stdout)
        for prog_number, prog_cmd in numbered_prog_cmds
    ]
    return [await f for f in asyncio.as_completed(programs)]


def find_difference(checker_cmd, filenames):
    for i in range(1, len(filenames)):
        diff = subprocess.Popen([*checker_cmd, filenames[i - 1], filenames[i]],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=script_directory())
        diff.wait()
        if diff.returncode:
            return filenames[i - 1], filenames[i]


def run_test(gen_cmd, checker_cmd, numbered_prog_cmds, ignore_err):
    input = get_testdata(gen_cmd)

    out_filenames = asyncio.run(
        save_outputs(numbered_prog_cmds, input, stdout=True))

    diff = find_difference(checker_cmd, out_filenames)

    if not diff and not ignore_err:
        err_filenames = asyncio.run(
            save_outputs(numbered_prog_cmds, input, stdout=False))

        diff = find_difference(checker_cmd, err_filenames)

    if diff:
        with open("test.in", "wb+") as test_file:
            test_file.write(input)
        raise AssertionError(f"Files {diff[0]} and {diff[1]} differ.")
    return True


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")

    gen_cmd = config["GEN"]["command"]
    checker_cmd = [config["CHECKER"]["command"],
                   config["CHECKER"]["command_flags"]]

    prog_cmds = []
    index = 1
    while f"PROG{index}" in config:
        if "off" not in config[f"PROG{index}"]:
            prog_cmds.append((index, config[f"PROG{index}"]["command"]))
        index += 1
    if len(prog_cmds) < 2:
        raise FileNotFoundError("No enough programs to diff")

    ignore_errors = config["GENERAL"]["ignore_err"] == "True"

    tests_passed = 0
    while run_test(gen_cmd, checker_cmd, prog_cmds, ignore_errors):
        tests_passed += 1
        print(tests_passed)
