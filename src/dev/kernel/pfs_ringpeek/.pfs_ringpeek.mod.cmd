savedcmd_pfs_ringpeek.mod := printf '%s\n'   pfs_ringpeek.o | awk '!x[$$0]++ { print("./"$$0) }' > pfs_ringpeek.mod
