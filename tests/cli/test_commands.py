import subprocess


def stormctl(*args):
    command = ['stormctl']
    command.extend(args)
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )


def test_resource_ls(random_resources):
    proc = stormctl('resource', 'ls')

    lines = proc.stdout.split('\n')
    # The output of 'resource ls' contains the header (this is the reason for
    # the +1), plus any resources that were not created by us (this is the
    # reason for the >=)
    assert len(lines) >= len(random_resources) + 1

    for res in random_resources:
        # Find the line in the output that correspond to this resource
        matching_lines = [
            line for line in lines if line.startswith(res.id)
        ]

        assert len(matching_lines) == 1
        res_line, = matching_lines

        # Check that this line contains at least one of the names of this
        # resource. It may not contain all the names because, if too long,
        # they will be truncated.
        if res.names:
            assert any(name in res_line for name in res.names)


def test_import(examples_path):
    stormctl('import', '-f', examples_path / 'hello-world.yaml')
