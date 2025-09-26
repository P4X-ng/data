export type BrefFlag = number;
export interface BrefEntry {
    off: bigint;
    len: number;
    flags: BrefFlag;
}
export interface BlobFingerprint {
    name: string;
    size: number;
    seed: number;
}
export interface IprogWindow {
    idx: number;
    hash16?: string;
    bref?: Array<[number, number, number]>;
    pvrt?: string;
    proto?: string;
}
export interface IprogPlan {
    type: 'iprog';
    file?: string;
    size: number;
    sha256: string;
    window_size: number;
    blob: BlobFingerprint;
    windows: IprogWindow[];
}
export interface PrefaceOptions {
    transferId: string;
    channels?: number;
    channelId?: number;
    blob: string;
    objectSha256: string;
    psk?: string;
    anchor?: bigint | number;
}
export interface SendResult {
    ok: boolean;
    bytesSent: number;
    elapsedS: number;
}
