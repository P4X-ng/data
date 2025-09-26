import type { IprogPlan, SendResult } from './types';
import type { WebSocketLike } from './wsAdapters';
export declare class PfsArithClient {
    private wsFactory;
    constructor(wsFactory: (url: string) => WebSocketLike);
    sendIprog(url: string, iprog: IprogPlan, transferId: string): Promise<SendResult>;
    sendIprogMulti(url: string, iprog: IprogPlan, transferId: string, channels?: number): Promise<SendResult>;
}
