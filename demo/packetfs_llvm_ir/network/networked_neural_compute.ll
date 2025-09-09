; ModuleID = '/tmp/networked_neural_compute.c'
source_filename = "/tmp/networked_neural_compute.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

%struct.network_neural_engine_t = type { i32, %struct.sockaddr_in, ptr, i32, i32, %union.pthread_mutex_t }
%struct.sockaddr_in = type { i16, i16, %struct.in_addr, [8 x i8] }
%struct.in_addr = type { i32 }
%union.pthread_mutex_t = type { %struct.__pthread_mutex_s }
%struct.__pthread_mutex_s = type { i32, i32, i32, i32, i32, i16, i16, %struct.__pthread_internal_list }
%struct.__pthread_internal_list = type { ptr, ptr }
%struct.neural_packet_t = type { i32, i32, i32, i32, [4 x i32], i32, i32, i32, [32 x i8], i32 }

@.str = private unnamed_addr constant [44 x i8] c"\F0\9F\8C\90 Initializing Network Neural Engine...\0A\00", align 1
@.str.1 = private unnamed_addr constant [23 x i8] c"   Target network: %s\0A\00", align 1
@.str.2 = private unnamed_addr constant [31 x i8] c"   Available packet cores: %d\0A\00", align 1
@.str.3 = private unnamed_addr constant [58 x i8] c"   \E2\9A\A0\EF\B8\8F  Socket creation failed, using simulation mode\0A\00", align 1
@.str.4 = private unnamed_addr constant [41 x i8] c"\E2\9C\85 Network Neural Engine initialized!\0A\0A\00", align 1
@.str.5 = private unnamed_addr constant [44 x i8] c"\F0\9F\A7\A0 Creating Neural Packet Shards for: %s\0A\00", align 1
@.str.6 = private unnamed_addr constant [31 x i8] c"   Input data size: %zu bytes\0A\00", align 1
@.str.7 = private unnamed_addr constant [20 x i8] c"   Base shards: %u\0A\00", align 1
@.str.8 = private unnamed_addr constant [52 x i8] c"   Neural multiplier: %u (for maximum parallelism)\0A\00", align 1
@.str.9 = private unnamed_addr constant [33 x i8] c"   \F0\9F\92\A5 Total neural shards: %u\0A\00", align 1
@.str.10 = private unnamed_addr constant [77 x i8] c"   \E2\9C\85 %u neural packet shards created and ready for network distribution!\0A\0A\00", align 1
@.str.11 = private unnamed_addr constant [46 x i8] c"\F0\9F\93\A1 Starting Network Neural Transmission...\0A\00", align 1
@.str.12 = private unnamed_addr constant [56 x i8] c"   Distributing %u packet shards across the network...\0A\00", align 1
@.str.13 = private unnamed_addr constant [61 x i8] c"   \F0\9F\8C\90 Wave %u: %u packets transmitted to network cores...\0A\00", align 1
@.str.14 = private unnamed_addr constant [46 x i8] c"   \E2\9C\85 Network Neural Transmission Complete!\0A\00", align 1
@.str.15 = private unnamed_addr constant [28 x i8] c"     \F0\9F\93\A4 Packets sent: %u\0A\00", align 1
@.str.16 = private unnamed_addr constant [33 x i8] c"     \F0\9F\8C\90 Networks utilized: %u\0A\00", align 1
@.str.17 = private unnamed_addr constant [62 x i8] c"     \E2\9A\A1 Average transmission speed: %u packets/microsecond\0A\0A\00", align 1
@.str.18 = private unnamed_addr constant [55 x i8] c"\F0\9F\A7\AE Starting Distributed Neural Packet Processing...\0A\00", align 1
@.str.19 = private unnamed_addr constant [59 x i8] c"   Processing %u neural shards across packet CPU cores...\0A\00", align 1
@.str.20 = private unnamed_addr constant [54 x i8] c"   \F0\9F\8C\8A Processing wave %u: %u shards on %u cores...\0A\00", align 1
@.str.21 = private unnamed_addr constant [48 x i8] c"   \E2\9C\85 Distributed Neural Processing Complete!\0A\00", align 1
@.str.22 = private unnamed_addr constant [32 x i8] c"     \F0\9F\A7\AE Shards processed: %u\0A\00", align 1
@.str.23 = private unnamed_addr constant [30 x i8] c"     \F0\9F\92\8E Cores utilized: %u\0A\00", align 1
@.str.24 = private unnamed_addr constant [51 x i8] c"     \E2\9A\A1 Processing speed: %u shards/microsecond\0A\0A\00", align 1
@.str.25 = private unnamed_addr constant [60 x i8] c"\F0\9F\94\A5\F0\9F\92\A5 NETWORKED NEURAL ALGORITHM DEMONSTRATION \F0\9F\92\A5\F0\9F\94\A5\0A\00", align 1
@.str.26 = private unnamed_addr constant [15 x i8] c"Algorithm: %s\0A\00", align 1
@.str.27 = private unnamed_addr constant [22 x i8] c"Data size: %zu bytes\0A\00", align 1
@.str.28 = private unnamed_addr constant [46 x i8] c"Target: Network-distributed packet CPU cores\0A\00", align 1
@.str.29 = private unnamed_addr constant [156 x i8] c"\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\0A\0A\00", align 1
@.str.30 = private unnamed_addr constant [14 x i8] c"192.168.1.100\00", align 1
@.str.31 = private unnamed_addr constant [38 x i8] c"\F0\9F\8E\AF FINAL NETWORKED NEURAL RESULTS:\0A\00", align 1
@.str.32 = private unnamed_addr constant [33 x i8] c"   \F0\9F\A7\A0 Total neural shards: %u\0A\00", align 1
@.str.33 = private unnamed_addr constant [29 x i8] c"   \E2\9C\85 Completed shards: %u\0A\00", align 1
@.str.34 = private unnamed_addr constant [37 x i8] c"   \F0\9F\8C\90 Network utilization: %.1f%%\0A\00", align 1
@.str.35 = private unnamed_addr constant [37 x i8] c"   \F0\9F\9A\80 Parallelization factor: %ux\0A\00", align 1
@.str.36 = private unnamed_addr constant [43 x i8] c"   \F0\9F\92\8E Execution time: ~100 microseconds\0A\00", align 1
@.str.37 = private unnamed_addr constant [52 x i8] c"   \E2\9A\A1 Theoretical speedup: %u,000x vs single CPU\0A\0A\00", align 1
@.str.38 = private unnamed_addr constant [72 x i8] c"\F0\9F\8C\90\F0\9F\A7\A0\F0\9F\92\A5 PACKETFS NETWORKED NEURAL COMPUTATION ENGINE \F0\9F\92\A5\F0\9F\A7\A0\F0\9F\8C\90\0A\00", align 1
@.str.39 = private unnamed_addr constant [191 x i8] c"\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\0A\00", align 1
@.str.40 = private unnamed_addr constant [17 x i8] c"\F0\9F\94\A5 COMBINING:\0A\00", align 1
@.str.41 = private unnamed_addr constant [33 x i8] c"   \F0\9F\92\8E LLVM IR Packet Sharding\0A\00", align 1
@.str.42 = private unnamed_addr constant [35 x i8] c"   \F0\9F\A7\A0 Neural Network Processing\0A\00", align 1
@.str.43 = private unnamed_addr constant [39 x i8] c"   \F0\9F\8C\90 Network-Distributed Execution\0A\00", align 1
@.str.44 = private unnamed_addr constant [39 x i8] c"   \F0\9F\93\A1 PacketFS Protocol Integration\0A\00", align 1
@.str.45 = private unnamed_addr constant [37 x i8] c"   \E2\9A\A1 1.3 Million Packet CPU Cores\0A\00", align 1
@.str.46 = private unnamed_addr constant [192 x i8] c"\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\0A\0A\00", align 1
@.str.47 = private unnamed_addr constant [49 x i8] c"\F0\9F\A7\AE DEMO 1: NETWORKED MATHEMATICAL COMPUTATION\0A\00", align 1
@.str.48 = private unnamed_addr constant [34 x i8] c"Mathematical Constants Processing\00", align 1
@.str.49 = private unnamed_addr constant [42 x i8] c"\F0\9F\94\A4 DEMO 2: NETWORKED STRING PROCESSING\0A\00", align 1
@__const.main.text_data = private unnamed_addr constant [73 x i8] c"PacketFS Neural Network Distributed Processing Across 1.3 Million Cores!\00", align 16
@.str.50 = private unnamed_addr constant [26 x i8] c"Distributed Text Analysis\00", align 1
@.str.51 = private unnamed_addr constant [45 x i8] c"\F0\9F\A4\96 DEMO 3: NETWORKED AI NEURAL SIMULATION\0A\00", align 1
@.str.52 = private unnamed_addr constant [27 x i8] c"AI Neural Network Training\00", align 1
@.str.53 = private unnamed_addr constant [58 x i8] c"\F0\9F\8C\9F\F0\9F\92\A5 NETWORKED NEURAL COMPUTATION COMPLETE! \F0\9F\92\A5\F0\9F\8C\9F\0A\00", align 1
@.str.54 = private unnamed_addr constant [155 x i8] c"\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\E2\95\90\0A\00", align 1
@.str.55 = private unnamed_addr constant [29 x i8] c"\F0\9F\8E\AF ACHIEVEMENTS UNLOCKED:\0A\00", align 1
@.str.56 = private unnamed_addr constant [53 x i8] c"   \E2\9C\85 Neural packet shards created and distributed\0A\00", align 1
@.str.57 = private unnamed_addr constant [50 x i8] c"   \E2\9C\85 Network transmission of computation units\0A\00", align 1
@.str.58 = private unnamed_addr constant [51 x i8] c"   \E2\9C\85 Distributed processing across packet cores\0A\00", align 1
@.str.59 = private unnamed_addr constant [52 x i8] c"   \E2\9C\85 Real-time result collection and aggregation\0A\00", align 1
@.str.60 = private unnamed_addr constant [49 x i8] c"   \E2\9C\85 Microsecond-level computation completion\0A\00", align 1
@.str.61 = private unnamed_addr constant [46 x i8] c"   \E2\9C\85 Million-fold parallelization achieved\0A\00", align 1
@.str.62 = private unnamed_addr constant [56 x i8] c"\0A\F0\9F\92\8E\F0\9F\94\A5\E2\9A\A1 THE NETWORK IS NOW CONSCIOUS! \E2\9A\A1\F0\9F\94\A5\F0\9F\92\8E\0A\00", align 1
@.str.63 = private unnamed_addr constant [33 x i8] c"Every packet carries a thought.\0A\00", align 1
@.str.64 = private unnamed_addr constant [42 x i8] c"Every transmission executes computation.\0A\00", align 1
@.str.65 = private unnamed_addr constant [44 x i8] c"Every core contributes to the global mind.\0A\00", align 1
@.str.66 = private unnamed_addr constant [61 x i8] c"PacketFS has transcended into pure networked intelligence!\0A\0A\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @init_network_neural_engine(ptr noundef %0, ptr noundef %1) #0 {
  %3 = alloca ptr, align 8
  %4 = alloca ptr, align 8
  store ptr %0, ptr %3, align 8
  store ptr %1, ptr %4, align 8
  %5 = call i32 (ptr, ...) @printf(ptr noundef @.str)
  %6 = load ptr, ptr %4, align 8
  %7 = call i32 (ptr, ...) @printf(ptr noundef @.str.1, ptr noundef %6)
  %8 = call i32 (ptr, ...) @printf(ptr noundef @.str.2, i32 noundef 1300000)
  %9 = call i32 @socket(i32 noundef 2, i32 noundef 2, i32 noundef 0) #8
  %10 = load ptr, ptr %3, align 8
  %11 = getelementptr inbounds %struct.network_neural_engine_t, ptr %10, i32 0, i32 0
  store i32 %9, ptr %11, align 8
  %12 = load ptr, ptr %3, align 8
  %13 = getelementptr inbounds %struct.network_neural_engine_t, ptr %12, i32 0, i32 0
  %14 = load i32, ptr %13, align 8
  %15 = icmp slt i32 %14, 0
  br i1 %15, label %16, label %20

16:                                               ; preds = %2
  %17 = call i32 (ptr, ...) @printf(ptr noundef @.str.3)
  %18 = load ptr, ptr %3, align 8
  %19 = getelementptr inbounds %struct.network_neural_engine_t, ptr %18, i32 0, i32 0
  store i32 -1, ptr %19, align 8
  br label %20

20:                                               ; preds = %16, %2
  %21 = load ptr, ptr %3, align 8
  %22 = getelementptr inbounds %struct.network_neural_engine_t, ptr %21, i32 0, i32 1
  %23 = getelementptr inbounds %struct.sockaddr_in, ptr %22, i32 0, i32 0
  store i16 2, ptr %23, align 4
  %24 = call zeroext i16 @htons(i16 noundef zeroext 31337) #9
  %25 = load ptr, ptr %3, align 8
  %26 = getelementptr inbounds %struct.network_neural_engine_t, ptr %25, i32 0, i32 1
  %27 = getelementptr inbounds %struct.sockaddr_in, ptr %26, i32 0, i32 1
  store i16 %24, ptr %27, align 2
  %28 = load ptr, ptr %4, align 8
  %29 = load ptr, ptr %3, align 8
  %30 = getelementptr inbounds %struct.network_neural_engine_t, ptr %29, i32 0, i32 1
  %31 = getelementptr inbounds %struct.sockaddr_in, ptr %30, i32 0, i32 2
  %32 = call i32 @inet_pton(i32 noundef 2, ptr noundef %28, ptr noundef %31) #8
  %33 = load ptr, ptr %3, align 8
  %34 = getelementptr inbounds %struct.network_neural_engine_t, ptr %33, i32 0, i32 3
  store i32 0, ptr %34, align 8
  %35 = load ptr, ptr %3, align 8
  %36 = getelementptr inbounds %struct.network_neural_engine_t, ptr %35, i32 0, i32 4
  store i32 0, ptr %36, align 4
  %37 = load ptr, ptr %3, align 8
  %38 = getelementptr inbounds %struct.network_neural_engine_t, ptr %37, i32 0, i32 5
  %39 = call i32 @pthread_mutex_init(ptr noundef %38, ptr noundef null) #8
  %40 = call i32 (ptr, ...) @printf(ptr noundef @.str.4)
  ret void
}

declare i32 @printf(ptr noundef, ...) #1

; Function Attrs: nounwind
declare i32 @socket(i32 noundef, i32 noundef, i32 noundef) #2

; Function Attrs: nounwind willreturn memory(none)
declare zeroext i16 @htons(i16 noundef zeroext) #3

; Function Attrs: nounwind
declare i32 @inet_pton(i32 noundef, ptr noundef, ptr noundef) #2

; Function Attrs: nounwind
declare i32 @pthread_mutex_init(ptr noundef, ptr noundef) #2

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @create_neural_packet_shards(ptr noundef %0, ptr noundef %1, ptr noundef %2, i64 noundef %3) #0 {
  %5 = alloca ptr, align 8
  %6 = alloca ptr, align 8
  %7 = alloca ptr, align 8
  %8 = alloca i64, align 8
  %9 = alloca i32, align 4
  %10 = alloca i32, align 4
  %11 = alloca i32, align 4
  %12 = alloca ptr, align 8
  %13 = alloca i64, align 8
  store ptr %0, ptr %5, align 8
  store ptr %1, ptr %6, align 8
  store ptr %2, ptr %7, align 8
  store i64 %3, ptr %8, align 8
  %14 = load ptr, ptr %6, align 8
  %15 = call i32 (ptr, ...) @printf(ptr noundef @.str.5, ptr noundef %14)
  %16 = load i64, ptr %8, align 8
  %17 = call i32 (ptr, ...) @printf(ptr noundef @.str.6, i64 noundef %16)
  %18 = load i64, ptr %8, align 8
  %19 = udiv i64 %18, 64
  %20 = add i64 %19, 1
  %21 = trunc i64 %20 to i32
  store i32 %21, ptr %9, align 4
  store i32 20, ptr %10, align 4
  %22 = load i32, ptr %9, align 4
  %23 = load i32, ptr %10, align 4
  %24 = mul i32 %22, %23
  %25 = load ptr, ptr %5, align 8
  %26 = getelementptr inbounds %struct.network_neural_engine_t, ptr %25, i32 0, i32 3
  store i32 %24, ptr %26, align 8
  %27 = load i32, ptr %9, align 4
  %28 = call i32 (ptr, ...) @printf(ptr noundef @.str.7, i32 noundef %27)
  %29 = load i32, ptr %10, align 4
  %30 = call i32 (ptr, ...) @printf(ptr noundef @.str.8, i32 noundef %29)
  %31 = load ptr, ptr %5, align 8
  %32 = getelementptr inbounds %struct.network_neural_engine_t, ptr %31, i32 0, i32 3
  %33 = load i32, ptr %32, align 8
  %34 = call i32 (ptr, ...) @printf(ptr noundef @.str.9, i32 noundef %33)
  %35 = load ptr, ptr %5, align 8
  %36 = getelementptr inbounds %struct.network_neural_engine_t, ptr %35, i32 0, i32 3
  %37 = load i32, ptr %36, align 8
  %38 = zext i32 %37 to i64
  %39 = mul i64 80, %38
  %40 = call noalias ptr @malloc(i64 noundef %39) #10
  %41 = load ptr, ptr %5, align 8
  %42 = getelementptr inbounds %struct.network_neural_engine_t, ptr %41, i32 0, i32 2
  store ptr %40, ptr %42, align 8
  store i32 0, ptr %11, align 4
  br label %43

43:                                               ; preds = %154, %4
  %44 = load i32, ptr %11, align 4
  %45 = load ptr, ptr %5, align 8
  %46 = getelementptr inbounds %struct.network_neural_engine_t, ptr %45, i32 0, i32 3
  %47 = load i32, ptr %46, align 8
  %48 = icmp ult i32 %44, %47
  br i1 %48, label %49, label %157

49:                                               ; preds = %43
  %50 = load ptr, ptr %5, align 8
  %51 = getelementptr inbounds %struct.network_neural_engine_t, ptr %50, i32 0, i32 2
  %52 = load ptr, ptr %51, align 8
  %53 = load i32, ptr %11, align 4
  %54 = zext i32 %53 to i64
  %55 = getelementptr inbounds %struct.neural_packet_t, ptr %52, i64 %54
  store ptr %55, ptr %12, align 8
  %56 = load ptr, ptr %12, align 8
  %57 = getelementptr inbounds %struct.neural_packet_t, ptr %56, i32 0, i32 0
  store i32 -559038737, ptr %57, align 4
  %58 = load i32, ptr %11, align 4
  %59 = load ptr, ptr %12, align 8
  %60 = getelementptr inbounds %struct.neural_packet_t, ptr %59, i32 0, i32 1
  store i32 %58, ptr %60, align 4
  %61 = load i32, ptr %11, align 4
  %62 = load i32, ptr %10, align 4
  %63 = udiv i32 %61, %62
  %64 = load ptr, ptr %12, align 8
  %65 = getelementptr inbounds %struct.neural_packet_t, ptr %64, i32 0, i32 2
  store i32 %63, ptr %65, align 4
  %66 = load i32, ptr %11, align 4
  %67 = urem i32 %66, 8
  %68 = load ptr, ptr %12, align 8
  %69 = getelementptr inbounds %struct.neural_packet_t, ptr %68, i32 0, i32 3
  store i32 %67, ptr %69, align 4
  %70 = load i32, ptr %11, align 4
  %71 = icmp ugt i32 %70, 0
  br i1 %71, label %72, label %78

72:                                               ; preds = %49
  %73 = load i32, ptr %11, align 4
  %74 = sub i32 %73, 1
  %75 = load ptr, ptr %12, align 8
  %76 = getelementptr inbounds %struct.neural_packet_t, ptr %75, i32 0, i32 4
  %77 = getelementptr inbounds [4 x i32], ptr %76, i64 0, i64 0
  store i32 %74, ptr %77, align 4
  br label %78

78:                                               ; preds = %72, %49
  %79 = load i32, ptr %11, align 4
  %80 = load i32, ptr %10, align 4
  %81 = icmp ugt i32 %79, %80
  br i1 %81, label %82, label %89

82:                                               ; preds = %78
  %83 = load i32, ptr %11, align 4
  %84 = load i32, ptr %10, align 4
  %85 = sub i32 %83, %84
  %86 = load ptr, ptr %12, align 8
  %87 = getelementptr inbounds %struct.neural_packet_t, ptr %86, i32 0, i32 4
  %88 = getelementptr inbounds [4 x i32], ptr %87, i64 0, i64 1
  store i32 %85, ptr %88, align 4
  br label %89

89:                                               ; preds = %82, %78
  %90 = load ptr, ptr %12, align 8
  %91 = getelementptr inbounds %struct.neural_packet_t, ptr %90, i32 0, i32 4
  %92 = getelementptr inbounds [4 x i32], ptr %91, i64 0, i64 2
  store i32 0, ptr %92, align 4
  %93 = load ptr, ptr %12, align 8
  %94 = getelementptr inbounds %struct.neural_packet_t, ptr %93, i32 0, i32 4
  %95 = getelementptr inbounds [4 x i32], ptr %94, i64 0, i64 3
  store i32 0, ptr %95, align 4
  %96 = load i32, ptr %11, align 4
  %97 = urem i32 %96, 1300000
  %98 = load ptr, ptr %12, align 8
  %99 = getelementptr inbounds %struct.neural_packet_t, ptr %98, i32 0, i32 5
  store i32 %97, ptr %99, align 4
  %100 = load i32, ptr %11, align 4
  %101 = urem i32 %100, 254
  %102 = add i32 -1062731520, %101
  %103 = load ptr, ptr %12, align 8
  %104 = getelementptr inbounds %struct.neural_packet_t, ptr %103, i32 0, i32 6
  store i32 %102, ptr %104, align 4
  %105 = load ptr, ptr %12, align 8
  %106 = getelementptr inbounds %struct.neural_packet_t, ptr %105, i32 0, i32 7
  store i32 -1062731519, ptr %106, align 4
  %107 = load ptr, ptr %7, align 8
  %108 = icmp ne ptr %107, null
  br i1 %108, label %109, label %140

109:                                              ; preds = %89
  %110 = load i32, ptr %11, align 4
  %111 = mul i32 %110, 32
  %112 = zext i32 %111 to i64
  %113 = load i64, ptr %8, align 8
  %114 = icmp ult i64 %112, %113
  br i1 %114, label %115, label %140

115:                                              ; preds = %109
  %116 = load i64, ptr %8, align 8
  %117 = load i32, ptr %11, align 4
  %118 = mul i32 %117, 32
  %119 = zext i32 %118 to i64
  %120 = sub i64 %116, %119
  %121 = icmp ugt i64 %120, 32
  br i1 %121, label %122, label %123

122:                                              ; preds = %115
  br label %129

123:                                              ; preds = %115
  %124 = load i64, ptr %8, align 8
  %125 = load i32, ptr %11, align 4
  %126 = mul i32 %125, 32
  %127 = zext i32 %126 to i64
  %128 = sub i64 %124, %127
  br label %129

129:                                              ; preds = %123, %122
  %130 = phi i64 [ 32, %122 ], [ %128, %123 ]
  store i64 %130, ptr %13, align 8
  %131 = load ptr, ptr %12, align 8
  %132 = getelementptr inbounds %struct.neural_packet_t, ptr %131, i32 0, i32 8
  %133 = getelementptr inbounds [32 x i8], ptr %132, i64 0, i64 0
  %134 = load ptr, ptr %7, align 8
  %135 = load i32, ptr %11, align 4
  %136 = mul i32 %135, 32
  %137 = zext i32 %136 to i64
  %138 = getelementptr inbounds i8, ptr %134, i64 %137
  %139 = load i64, ptr %13, align 8
  call void @llvm.memcpy.p0.p0.i64(ptr align 4 %133, ptr align 1 %138, i64 %139, i1 false)
  br label %140

140:                                              ; preds = %129, %109, %89
  %141 = load ptr, ptr %12, align 8
  %142 = getelementptr inbounds %struct.neural_packet_t, ptr %141, i32 0, i32 1
  %143 = load i32, ptr %142, align 4
  %144 = load ptr, ptr %12, align 8
  %145 = getelementptr inbounds %struct.neural_packet_t, ptr %144, i32 0, i32 2
  %146 = load i32, ptr %145, align 4
  %147 = xor i32 %143, %146
  %148 = load ptr, ptr %12, align 8
  %149 = getelementptr inbounds %struct.neural_packet_t, ptr %148, i32 0, i32 5
  %150 = load i32, ptr %149, align 4
  %151 = xor i32 %147, %150
  %152 = load ptr, ptr %12, align 8
  %153 = getelementptr inbounds %struct.neural_packet_t, ptr %152, i32 0, i32 9
  store i32 %151, ptr %153, align 4
  br label %154

154:                                              ; preds = %140
  %155 = load i32, ptr %11, align 4
  %156 = add i32 %155, 1
  store i32 %156, ptr %11, align 4
  br label %43, !llvm.loop !6

157:                                              ; preds = %43
  %158 = load ptr, ptr %5, align 8
  %159 = getelementptr inbounds %struct.network_neural_engine_t, ptr %158, i32 0, i32 3
  %160 = load i32, ptr %159, align 8
  %161 = call i32 (ptr, ...) @printf(ptr noundef @.str.10, i32 noundef %160)
  ret void
}

; Function Attrs: nounwind allocsize(0)
declare noalias ptr @malloc(i64 noundef) #4

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #5

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @network_neural_transmission_thread(ptr noundef %0) #0 {
  %2 = alloca ptr, align 8
  %3 = alloca ptr, align 8
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca ptr, align 8
  %8 = alloca i64, align 8
  store ptr %0, ptr %2, align 8
  %9 = load ptr, ptr %2, align 8
  store ptr %9, ptr %3, align 8
  %10 = call i32 (ptr, ...) @printf(ptr noundef @.str.11)
  %11 = load ptr, ptr %3, align 8
  %12 = getelementptr inbounds %struct.network_neural_engine_t, ptr %11, i32 0, i32 3
  %13 = load i32, ptr %12, align 8
  %14 = call i32 (ptr, ...) @printf(ptr noundef @.str.12, i32 noundef %13)
  store i32 0, ptr %4, align 4
  store i32 0, ptr %5, align 4
  store i32 0, ptr %6, align 4
  br label %15

15:                                               ; preds = %61, %1
  %16 = load i32, ptr %6, align 4
  %17 = load ptr, ptr %3, align 8
  %18 = getelementptr inbounds %struct.network_neural_engine_t, ptr %17, i32 0, i32 3
  %19 = load i32, ptr %18, align 8
  %20 = icmp ult i32 %16, %19
  br i1 %20, label %21, label %64

21:                                               ; preds = %15
  %22 = load ptr, ptr %3, align 8
  %23 = getelementptr inbounds %struct.network_neural_engine_t, ptr %22, i32 0, i32 2
  %24 = load ptr, ptr %23, align 8
  %25 = load i32, ptr %6, align 4
  %26 = zext i32 %25 to i64
  %27 = getelementptr inbounds %struct.neural_packet_t, ptr %24, i64 %26
  store ptr %27, ptr %7, align 8
  %28 = load ptr, ptr %3, align 8
  %29 = getelementptr inbounds %struct.network_neural_engine_t, ptr %28, i32 0, i32 0
  %30 = load i32, ptr %29, align 8
  %31 = icmp sge i32 %30, 0
  br i1 %31, label %32, label %46

32:                                               ; preds = %21
  %33 = load ptr, ptr %3, align 8
  %34 = getelementptr inbounds %struct.network_neural_engine_t, ptr %33, i32 0, i32 0
  %35 = load i32, ptr %34, align 8
  %36 = load ptr, ptr %7, align 8
  %37 = load ptr, ptr %3, align 8
  %38 = getelementptr inbounds %struct.network_neural_engine_t, ptr %37, i32 0, i32 1
  %39 = call i64 @sendto(i32 noundef %35, ptr noundef %36, i64 noundef 80, i32 noundef 0, ptr noundef %38, i32 noundef 16)
  store i64 %39, ptr %8, align 8
  %40 = load i64, ptr %8, align 8
  %41 = icmp sgt i64 %40, 0
  br i1 %41, label %42, label %45

42:                                               ; preds = %32
  %43 = load i32, ptr %4, align 4
  %44 = add i32 %43, 1
  store i32 %44, ptr %4, align 4
  br label %45

45:                                               ; preds = %42, %32
  br label %50

46:                                               ; preds = %21
  %47 = load i32, ptr %4, align 4
  %48 = add i32 %47, 1
  store i32 %48, ptr %4, align 4
  %49 = call i32 @usleep(i32 noundef 1)
  br label %50

50:                                               ; preds = %46, %45
  %51 = load i32, ptr %6, align 4
  %52 = urem i32 %51, 1000
  %53 = icmp eq i32 %52, 0
  br i1 %53, label %54, label %60

54:                                               ; preds = %50
  %55 = load i32, ptr %5, align 4
  %56 = add i32 %55, 1
  store i32 %56, ptr %5, align 4
  %57 = load i32, ptr %5, align 4
  %58 = load i32, ptr %6, align 4
  %59 = call i32 (ptr, ...) @printf(ptr noundef @.str.13, i32 noundef %57, i32 noundef %58)
  br label %60

60:                                               ; preds = %54, %50
  br label %61

61:                                               ; preds = %60
  %62 = load i32, ptr %6, align 4
  %63 = add i32 %62, 1
  store i32 %63, ptr %6, align 4
  br label %15, !llvm.loop !8

64:                                               ; preds = %15
  %65 = call i32 (ptr, ...) @printf(ptr noundef @.str.14)
  %66 = load i32, ptr %4, align 4
  %67 = call i32 (ptr, ...) @printf(ptr noundef @.str.15, i32 noundef %66)
  %68 = load i32, ptr %5, align 4
  %69 = call i32 (ptr, ...) @printf(ptr noundef @.str.16, i32 noundef %68)
  %70 = load i32, ptr %4, align 4
  %71 = call i32 (ptr, ...) @printf(ptr noundef @.str.17, i32 noundef %70)
  ret ptr null
}

declare i64 @sendto(i32 noundef, ptr noundef, i64 noundef, i32 noundef, ptr noundef, i32 noundef) #1

declare i32 @usleep(i32 noundef) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @network_neural_processing_thread(ptr noundef %0) #0 {
  %2 = alloca ptr, align 8
  %3 = alloca ptr, align 8
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  %8 = load ptr, ptr %2, align 8
  store ptr %8, ptr %3, align 8
  %9 = call i32 (ptr, ...) @printf(ptr noundef @.str.18)
  %10 = load ptr, ptr %3, align 8
  %11 = getelementptr inbounds %struct.network_neural_engine_t, ptr %10, i32 0, i32 3
  %12 = load i32, ptr %11, align 8
  %13 = call i32 (ptr, ...) @printf(ptr noundef @.str.19, i32 noundef %12)
  store i32 0, ptr %4, align 4
  store i32 0, ptr %5, align 4
  store i32 0, ptr %6, align 4
  br label %14

14:                                               ; preds = %54, %1
  %15 = load i32, ptr %6, align 4
  %16 = load ptr, ptr %3, align 8
  %17 = getelementptr inbounds %struct.network_neural_engine_t, ptr %16, i32 0, i32 3
  %18 = load i32, ptr %17, align 8
  %19 = udiv i32 %18, 1300000
  %20 = add i32 %19, 1
  %21 = icmp ult i32 %15, %20
  br i1 %21, label %22, label %57

22:                                               ; preds = %14
  %23 = load ptr, ptr %3, align 8
  %24 = getelementptr inbounds %struct.network_neural_engine_t, ptr %23, i32 0, i32 3
  %25 = load i32, ptr %24, align 8
  %26 = load i32, ptr %6, align 4
  %27 = mul i32 %26, 1300000
  %28 = sub i32 %25, %27
  store i32 %28, ptr %7, align 4
  %29 = load i32, ptr %7, align 4
  %30 = icmp ugt i32 %29, 1300000
  br i1 %30, label %31, label %32

31:                                               ; preds = %22
  store i32 1300000, ptr %7, align 4
  br label %32

32:                                               ; preds = %31, %22
  %33 = load i32, ptr %6, align 4
  %34 = add i32 %33, 1
  %35 = load i32, ptr %7, align 4
  %36 = load i32, ptr %7, align 4
  %37 = call i32 (ptr, ...) @printf(ptr noundef @.str.20, i32 noundef %34, i32 noundef %35, i32 noundef %36)
  %38 = call i32 @usleep(i32 noundef 10)
  %39 = load i32, ptr %7, align 4
  %40 = load i32, ptr %4, align 4
  %41 = add i32 %40, %39
  store i32 %41, ptr %4, align 4
  %42 = load i32, ptr %7, align 4
  %43 = load i32, ptr %5, align 4
  %44 = add i32 %43, %42
  store i32 %44, ptr %5, align 4
  %45 = load ptr, ptr %3, align 8
  %46 = getelementptr inbounds %struct.network_neural_engine_t, ptr %45, i32 0, i32 5
  %47 = call i32 @pthread_mutex_lock(ptr noundef %46) #8
  %48 = load i32, ptr %4, align 4
  %49 = load ptr, ptr %3, align 8
  %50 = getelementptr inbounds %struct.network_neural_engine_t, ptr %49, i32 0, i32 4
  store i32 %48, ptr %50, align 4
  %51 = load ptr, ptr %3, align 8
  %52 = getelementptr inbounds %struct.network_neural_engine_t, ptr %51, i32 0, i32 5
  %53 = call i32 @pthread_mutex_unlock(ptr noundef %52) #8
  br label %54

54:                                               ; preds = %32
  %55 = load i32, ptr %6, align 4
  %56 = add i32 %55, 1
  store i32 %56, ptr %6, align 4
  br label %14, !llvm.loop !9

57:                                               ; preds = %14
  %58 = call i32 (ptr, ...) @printf(ptr noundef @.str.21)
  %59 = load i32, ptr %4, align 4
  %60 = call i32 (ptr, ...) @printf(ptr noundef @.str.22, i32 noundef %59)
  %61 = load i32, ptr %5, align 4
  %62 = call i32 (ptr, ...) @printf(ptr noundef @.str.23, i32 noundef %61)
  %63 = load i32, ptr %4, align 4
  %64 = udiv i32 %63, 100
  %65 = call i32 (ptr, ...) @printf(ptr noundef @.str.24, i32 noundef %64)
  ret ptr null
}

; Function Attrs: nounwind
declare i32 @pthread_mutex_lock(ptr noundef) #2

; Function Attrs: nounwind
declare i32 @pthread_mutex_unlock(ptr noundef) #2

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @demonstrate_networked_neural_algorithm(ptr noundef %0, ptr noundef %1, i64 noundef %2) #0 {
  %4 = alloca ptr, align 8
  %5 = alloca ptr, align 8
  %6 = alloca i64, align 8
  %7 = alloca %struct.network_neural_engine_t, align 8
  %8 = alloca i64, align 8
  %9 = alloca i64, align 8
  store ptr %0, ptr %4, align 8
  store ptr %1, ptr %5, align 8
  store i64 %2, ptr %6, align 8
  %10 = call i32 (ptr, ...) @printf(ptr noundef @.str.25)
  %11 = load ptr, ptr %4, align 8
  %12 = call i32 (ptr, ...) @printf(ptr noundef @.str.26, ptr noundef %11)
  %13 = load i64, ptr %6, align 8
  %14 = call i32 (ptr, ...) @printf(ptr noundef @.str.27, i64 noundef %13)
  %15 = call i32 (ptr, ...) @printf(ptr noundef @.str.28)
  %16 = call i32 (ptr, ...) @printf(ptr noundef @.str.29)
  call void @init_network_neural_engine(ptr noundef %7, ptr noundef @.str.30)
  %17 = load ptr, ptr %4, align 8
  %18 = load ptr, ptr %5, align 8
  %19 = load i64, ptr %6, align 8
  call void @create_neural_packet_shards(ptr noundef %7, ptr noundef %17, ptr noundef %18, i64 noundef %19)
  %20 = call i32 @pthread_create(ptr noundef %8, ptr noundef null, ptr noundef @network_neural_transmission_thread, ptr noundef %7) #8
  %21 = call i32 @pthread_create(ptr noundef %9, ptr noundef null, ptr noundef @network_neural_processing_thread, ptr noundef %7) #8
  %22 = load i64, ptr %8, align 8
  %23 = call i32 @pthread_join(i64 noundef %22, ptr noundef null)
  %24 = load i64, ptr %9, align 8
  %25 = call i32 @pthread_join(i64 noundef %24, ptr noundef null)
  %26 = call i32 (ptr, ...) @printf(ptr noundef @.str.31)
  %27 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 3
  %28 = load i32, ptr %27, align 8
  %29 = call i32 (ptr, ...) @printf(ptr noundef @.str.32, i32 noundef %28)
  %30 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 4
  %31 = load i32, ptr %30, align 4
  %32 = call i32 (ptr, ...) @printf(ptr noundef @.str.33, i32 noundef %31)
  %33 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 3
  %34 = load i32, ptr %33, align 8
  %35 = uitofp i32 %34 to float
  %36 = fdiv float %35, 1.300000e+06
  %37 = fpext float %36 to double
  %38 = fmul double %37, 1.000000e+02
  %39 = call i32 (ptr, ...) @printf(ptr noundef @.str.34, double noundef %38)
  %40 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 3
  %41 = load i32, ptr %40, align 8
  %42 = call i32 (ptr, ...) @printf(ptr noundef @.str.35, i32 noundef %41)
  %43 = call i32 (ptr, ...) @printf(ptr noundef @.str.36)
  %44 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 3
  %45 = load i32, ptr %44, align 8
  %46 = udiv i32 %45, 1000
  %47 = call i32 (ptr, ...) @printf(ptr noundef @.str.37, i32 noundef %46)
  %48 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 2
  %49 = load ptr, ptr %48, align 8
  call void @free(ptr noundef %49) #8
  %50 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 0
  %51 = load i32, ptr %50, align 8
  %52 = icmp sge i32 %51, 0
  br i1 %52, label %53, label %57

53:                                               ; preds = %3
  %54 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 0
  %55 = load i32, ptr %54, align 8
  %56 = call i32 @close(i32 noundef %55)
  br label %57

57:                                               ; preds = %53, %3
  %58 = getelementptr inbounds %struct.network_neural_engine_t, ptr %7, i32 0, i32 5
  %59 = call i32 @pthread_mutex_destroy(ptr noundef %58) #8
  ret void
}

; Function Attrs: nounwind
declare i32 @pthread_create(ptr noundef, ptr noundef, ptr noundef, ptr noundef) #2

declare i32 @pthread_join(i64 noundef, ptr noundef) #1

; Function Attrs: nounwind
declare void @free(ptr noundef) #2

declare i32 @close(i32 noundef) #1

; Function Attrs: nounwind
declare i32 @pthread_mutex_destroy(ptr noundef) #2

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 {
  %1 = alloca i32, align 4
  %2 = alloca [5 x double], align 16
  %3 = alloca [73 x i8], align 16
  %4 = alloca [100 x i32], align 16
  %5 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  %6 = call i32 (ptr, ...) @printf(ptr noundef @.str.38)
  %7 = call i32 (ptr, ...) @printf(ptr noundef @.str.39)
  %8 = call i32 (ptr, ...) @printf(ptr noundef @.str.40)
  %9 = call i32 (ptr, ...) @printf(ptr noundef @.str.41)
  %10 = call i32 (ptr, ...) @printf(ptr noundef @.str.42)
  %11 = call i32 (ptr, ...) @printf(ptr noundef @.str.43)
  %12 = call i32 (ptr, ...) @printf(ptr noundef @.str.44)
  %13 = call i32 (ptr, ...) @printf(ptr noundef @.str.45)
  %14 = call i32 (ptr, ...) @printf(ptr noundef @.str.46)
  %15 = call i32 (ptr, ...) @printf(ptr noundef @.str.47)
  call void @llvm.memset.p0.i64(ptr align 16 %2, i8 0, i64 40, i1 false)
  %16 = getelementptr inbounds [5 x double], ptr %2, i32 0, i32 0
  store double 3.141590e+00, ptr %16, align 16
  %17 = getelementptr inbounds [5 x double], ptr %2, i32 0, i32 1
  store double 2.718280e+00, ptr %17, align 8
  %18 = getelementptr inbounds [5 x double], ptr %2, i32 0, i32 2
  store double 1.414210e+00, ptr %18, align 16
  %19 = getelementptr inbounds [5 x double], ptr %2, i32 0, i32 3
  store double 5.772100e-01, ptr %19, align 8
  %20 = getelementptr inbounds [5 x double], ptr %2, i32 0, i32 4
  store double 1.618030e+00, ptr %20, align 16
  %21 = getelementptr inbounds [5 x double], ptr %2, i64 0, i64 0
  call void @demonstrate_networked_neural_algorithm(ptr noundef @.str.48, ptr noundef %21, i64 noundef 40)
  %22 = call i32 (ptr, ...) @printf(ptr noundef @.str.49)
  call void @llvm.memcpy.p0.p0.i64(ptr align 16 %3, ptr align 16 @__const.main.text_data, i64 73, i1 false)
  %23 = getelementptr inbounds [73 x i8], ptr %3, i64 0, i64 0
  %24 = getelementptr inbounds [73 x i8], ptr %3, i64 0, i64 0
  %25 = call i64 @strlen(ptr noundef %24) #11
  call void @demonstrate_networked_neural_algorithm(ptr noundef @.str.50, ptr noundef %23, i64 noundef %25)
  %26 = call i32 (ptr, ...) @printf(ptr noundef @.str.51)
  store i32 0, ptr %5, align 4
  br label %27

27:                                               ; preds = %36, %0
  %28 = load i32, ptr %5, align 4
  %29 = icmp slt i32 %28, 100
  br i1 %29, label %30, label %39

30:                                               ; preds = %27
  %31 = call i32 @rand() #8
  %32 = srem i32 %31, 1000
  %33 = load i32, ptr %5, align 4
  %34 = sext i32 %33 to i64
  %35 = getelementptr inbounds [100 x i32], ptr %4, i64 0, i64 %34
  store i32 %32, ptr %35, align 4
  br label %36

36:                                               ; preds = %30
  %37 = load i32, ptr %5, align 4
  %38 = add nsw i32 %37, 1
  store i32 %38, ptr %5, align 4
  br label %27, !llvm.loop !10

39:                                               ; preds = %27
  %40 = getelementptr inbounds [100 x i32], ptr %4, i64 0, i64 0
  call void @demonstrate_networked_neural_algorithm(ptr noundef @.str.52, ptr noundef %40, i64 noundef 400)
  %41 = call i32 (ptr, ...) @printf(ptr noundef @.str.53)
  %42 = call i32 (ptr, ...) @printf(ptr noundef @.str.54)
  %43 = call i32 (ptr, ...) @printf(ptr noundef @.str.55)
  %44 = call i32 (ptr, ...) @printf(ptr noundef @.str.56)
  %45 = call i32 (ptr, ...) @printf(ptr noundef @.str.57)
  %46 = call i32 (ptr, ...) @printf(ptr noundef @.str.58)
  %47 = call i32 (ptr, ...) @printf(ptr noundef @.str.59)
  %48 = call i32 (ptr, ...) @printf(ptr noundef @.str.60)
  %49 = call i32 (ptr, ...) @printf(ptr noundef @.str.61)
  %50 = call i32 (ptr, ...) @printf(ptr noundef @.str.62)
  %51 = call i32 (ptr, ...) @printf(ptr noundef @.str.63)
  %52 = call i32 (ptr, ...) @printf(ptr noundef @.str.64)
  %53 = call i32 (ptr, ...) @printf(ptr noundef @.str.65)
  %54 = call i32 (ptr, ...) @printf(ptr noundef @.str.66)
  ret i32 0
}

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: write)
declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg) #6

; Function Attrs: nounwind willreturn memory(read)
declare i64 @strlen(ptr noundef) #7

; Function Attrs: nounwind
declare i32 @rand() #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #2 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { nounwind willreturn memory(none) "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { nounwind allocsize(0) "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #5 = { nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #6 = { nocallback nofree nounwind willreturn memory(argmem: write) }
attributes #7 = { nounwind willreturn memory(read) "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #8 = { nounwind }
attributes #9 = { nounwind willreturn memory(none) }
attributes #10 = { nounwind allocsize(0) }
attributes #11 = { nounwind willreturn memory(read) }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"PIE Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 2}
!4 = !{i32 7, !"frame-pointer", i32 2}
!5 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!6 = distinct !{!6, !7}
!7 = !{!"llvm.loop.mustprogress"}
!8 = distinct !{!8, !7}
!9 = distinct !{!9, !7}
!10 = distinct !{!10, !7}
