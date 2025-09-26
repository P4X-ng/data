export declare const MAGIC_PREFACE: Uint8Array<ArrayBuffer>;
export declare const MAGIC_FRAME: Uint8Array<ArrayBuffer>;
export declare const VER = 1;
export declare const FLAG_CTRL = 1;
export declare const FLAG_DATA = 0;
export declare const PREFACE_FLAG_ANCHOR = 1;
export interface PrefaceParsed {
    version: number;
    flags: number;
    channels: number;
    channel_id: number;
    transfer_id: string;
    blob: string;
    object: string;
    psk: string;
    anchor: bigint;
}
export declare function buildPreface(opts: {
    transferId: string;
    channels: number;
    channelId: number;
    blob: string;
    objectSha256: string;
    psk?: string;
    anchor?: bigint | number;
    flags?: number;
}): Uint8Array;
export declare function parsePreface(data: Uint8Array): PrefaceParsed;
export interface ParsedFrame {
    seq: bigint;
    flags: number;
    payload: Uint8Array;
}
export declare function buildFramesFromData(data: Uint8Array, opts?: {
    startSeq?: bigint;
    windowSize?: number;
    flags?: number;
}): Uint8Array;
export declare function parseFramesConcat(buf: Uint8Array): ParsedFrame[];
export declare function buildCtrlJsonFrame(type: string, obj: Record<string, unknown>): Uint8Array;
export declare const CTRL_BIN_WIN = 161;
export declare const CTRL_BIN_END = 162;
export declare const CTRL_BIN_DONE = 163;
export declare function buildCtrlBinWin(idx: number): Uint8Array;
export declare function buildCtrlBinEnd(idx: number, hash16?: Uint8Array): Uint8Array;
export declare function buildCtrlBinDone(sha256: Uint8Array): Uint8Array;
export declare function parseCtrlBin(payload: Uint8Array): ["WIN", number, null] | ["END", number, Uint8Array] | ["DONE", null, string] | null;
export declare function isCtrl(flags: number): boolean;
