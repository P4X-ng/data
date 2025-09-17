savedcmd_r816x_peek.mod := printf '%s\n'   r816x_peek.o | awk '!x[$$0]++ { print("./"$$0) }' > r816x_peek.mod
