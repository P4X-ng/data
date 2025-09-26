# Minimal host build for OSv yeet tools (sender/listener)

CC      ?= gcc
CFLAGS  ?= -O3 -pipe -march=native -Wall -Wextra -Wno-unused-parameter
LDFLAGS ?=

SRC_DIR := src
INC_DIR := include
BIN_DIR := bin

SENDER_SRC := $(SRC_DIR)/yeet_sender.c
LISTEN_SRC := $(SRC_DIR)/yeet_listener.c
AFP_TX_SRC := $(SRC_DIR)/yeet_afp_tx.c
AFP_RX_SRC := $(SRC_DIR)/yeet_afp_rx.c
HEADERS   := $(INC_DIR)/proto.h $(INC_DIR)/afp.h $(INC_DIR)/pfs_raw.h

SENDER_BIN := $(BIN_DIR)/yeet_sender
LISTEN_BIN := $(BIN_DIR)/yeet_listener
AFP_TX_BIN := $(BIN_DIR)/yeet_afp_tx
AFP_RX_BIN := $(BIN_DIR)/yeet_afp_rx

.PHONY: all sender listener afp clean

all: $(SENDER_BIN) $(LISTEN_BIN) $(AFP_TX_BIN) $(AFP_RX_BIN)

sender: $(SENDER_BIN)
listener: $(LISTEN_BIN)
afp: $(AFP_TX_BIN) $(AFP_RX_BIN)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(SENDER_BIN): $(SENDER_SRC) $(HEADERS) | $(BIN_DIR)
	$(CC) $(CFLAGS) -I$(INC_DIR) -o $@ $(SENDER_SRC) $(LDFLAGS)

$(LISTEN_BIN): $(LISTEN_SRC) $(HEADERS) | $(BIN_DIR)
	$(CC) $(CFLAGS) -I$(INC_DIR) -o $@ $(LISTEN_SRC) $(LDFLAGS)

$(AFP_TX_BIN): $(AFP_TX_SRC) $(HEADERS) | $(BIN_DIR)
	$(CC) $(CFLAGS) -I$(INC_DIR) -o $@ $(AFP_TX_SRC) $(LDFLAGS)

$(AFP_RX_BIN): $(AFP_RX_SRC) $(HEADERS) | $(BIN_DIR)
	$(CC) $(CFLAGS) -I$(INC_DIR) -o $@ $(AFP_RX_SRC) $(LDFLAGS)

clean:
	rm -rf $(BIN_DIR)
