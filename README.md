csctester
=========
![alt text](https://cloudsignatureconsortium.org/wp-content/uploads/2018/09/logo_light.png "Cloud Signature Consortium")

Utility script for [Cloud Signature Consortium](https://cloudsignatureconsortium.org) API testing.

```
Usage: csctester3.py [OPTIONS] COMMAND [ARGS]...

  Utility script for Cloud Signature Consortium (CSC) API testing.

  If username/password, session or environment are not provided, a text user interface (TUI) will be shown.

  Returned values:
   0 →  OK
   1 →  Error: the script couldn't run properly (e.g. invalid login credentials)
   2 →  Error: one or more minor checks failed (e.g. wrong error messages)
   3 →  Critical error: core signature functionalities are compromised

  ARGS: with `check' command, the credential ID(s) to be tested. If no
  credential ID is provided then check every credential found in the account
  and perform other non credential-related checks

Options:
  -u, --user <username>         Account username to be used.
  -p, --passw <password>        Account password to be used.
  -e, --environment <env>       Target environment. Use the list command to
                                view the supported environments.
  -s, --session <session-key>   A valid CSC access token. If provided, no
                                authentication using username/password will be
                                performed.
  -q, --quiet                   Non-interactive mode: every test requiring a
                                user interaction will be skipped. Only
                                automatic credentials (PIN only) will be
                                checked using the default PIN. WARNING the
                                default PIN is 12345678.
  -l, --log <path-to-log-file>  Log file path. If present, the output will be
                                written to this file. If not, no log file will
                                be created and STDOUT will be used.
  -V, --version                 Print version information and exit.
  -h, --help                    Show this message and exit.

Commands:
  check  Check credential ID(s) provided: if no credential ID is provided then
         check every credential found in the account and perform other non
         credential-related checks
  list   List the available environments and exit
  logo   Check logo files and exit
  scan   Scan the user credentials: no signature test will be performed, only
         the credential details will be shown.
```
