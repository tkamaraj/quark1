# ISSUES

- RESOLVED - No idea how. See the comment at that place in the code - An empty string ("") being piped from a command will be considered as no STDIN because of the way data is passed through the communication pipe between the parent and child process. Might need to change it later.
- Large text somehow makes io.StringIO buffers empty.
- inp() in main.py still remains largely broken and missing core features.
- DONE - Do the improvements planned for `ls` (item type differentiation for both types of listing).
- Implement number of inode links, stat.st_nlink in `ls`.
