export interface WebSocketLike {
    send(data: Uint8Array): Promise<void>;
    recvJson(timeoutMs?: number): Promise<any>;
    recvText(timeoutMs?: number): Promise<string>;
}
export declare function browserWS(url: string): WebSocketLike;
