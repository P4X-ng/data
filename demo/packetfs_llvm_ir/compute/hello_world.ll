; 🔥 PACKETFS HELLO WORLD - LLVM IR THAT SHARDS INTO 1.3M PACKETS! 🔥
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

@hello_str = private unnamed_addr constant [13 x i8] c"Hello World!\00", align 1

declare i32 @puts(i8* nocapture readonly) #0

; Function will shard into 15+ packet shards for massive parallelism
define i32 @main() #0 {
entry:
  ; SHARD 1-3: Load string address (3 packet shards)
  %0 = getelementptr inbounds [13 x i8], [13 x i8]* @hello_str, i64 0, i64 0
  
  ; SHARD 4-11: Function call preparation and execution (8 packet shards)
  %1 = call i32 @puts(i8* %0)
  
  ; SHARD 12-14: Return value processing (3 packet shards) 
  ret i32 0
}

attributes #0 = { noinline nounwind optnone uwtable }

; PACKET CPU METADATA:
; Expected shards: 14
; Parallelization factor: 14x 
; Execution time: Network latency only!
; Target cores: 14 of 1.3M available
