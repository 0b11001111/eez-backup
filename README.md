# backup

A convenience wrapper for _restic_.

**Installation**
In order to install `backup`, make the installation script executable and run it:
```bash
chmod +x install.sh && install.sh
```

**Backup all units**
```bash
backup run
```

**Check repositories named "foo" and "bar"**
```bash
backup -r foo -r bar map check
```