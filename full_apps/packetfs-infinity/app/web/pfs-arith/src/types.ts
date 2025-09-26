export type BrefFlag = number;

export interface BrefEntry {
  off: bigint; // absolute or relative (signed) offset depending on flags
  len: number;
  flags: BrefFlag; // bit0: 1 => relative (delta from anchor), 0 => absolute
}

export interface BlobFingerprint {
  name: string;
  size: number; // bytes
  seed: number;
}

export interface IprogWindow {
  idx: number;
  hash16?: string; // hex
  bref?: Array<[number, number, number]>; // [off,len,flags]
  pvrt?: string; // base64 (optional)
  proto?: string; // base64 (optional)
}

export interface IprogPlan {
  type: 'iprog';
  file?: string;
  size: number;
  sha256: string; // hex
  window_size: number;
  blob: BlobFingerprint;
  windows: IprogWindow[];
}

export interface PrefaceOptions {
  transferId: string;
  channels?: number;
  channelId?: number;
  blob: string; // blob fingerprint string e.g. name:size:seed
  objectSha256: string; // hex
  psk?: string;
  anchor?: bigint | number; // optional anchor, default size/2
}

export interface SendResult {
  ok: boolean;
  bytesSent: number;
  elapsedS: number;
}
