export declare const MAGIC: Uint8Array<ArrayBuffer>;
export declare const SEC_RAW = 1;
export declare const SEC_PROTO = 2;
export declare const SEC_BREF = 3;
export interface BrefChunk {
    off: bigint;
    len: number;
    flags: number;
}
export declare function buildContainer(opts: {
    raw?: Uint8Array | null;
    proto?: Uint8Array | null;
    bref?: Array<BrefChunk> | null;
}): Uint8Array;
export declare function parseContainer(buf: Uint8Array): Map<number, Uint8Array>;
