# csctester

```
Usage: csctester3.py [OPTIONS] COMMAND [ARGS]...

  CSC test script

  Returned values:
   0 →  OK
   1 →  Error: the script couldn't run properly (e.g. invalid login credentials)
   2 →  Error: one or more minor checks failed (e.g. wrong error messages)
   3 →  Critical error: core signature functionalities are compromised

Options:
  -u, --user <username>        Account username to be used
  -p, --passw <password>       Account password to be used
  -e, --environment <env>      Target environment
  -s, --session <session-key>  A valid CSC access token
  -q, --quiet                  Non-interactive mode: every test requiring a
                               user interaction will be skipped
  -V, --version                Print version information and exit
  -h, --help                   Show this message and exit.

Commands:
  check  Check credentials provided: if no credential id(s) are provided then
         check all
  list   List the available environments and exit
  logo   Check logo files and exit
  scan   Scan user credentials
```
