/*
 * 🔥💀 LLVM IR PARSER FOR PACKET CPU COMPILATION 💀🔥
 * 
 * PARSE LLVM IR FROM ANY LANGUAGE:
 * - C/C++ compiled with clang -emit-llvm
 * - Rust compiled with --emit=llvm-ir  
 * - Go compiled with gollvm
 * - ANY LANGUAGE THAT COMPILES TO LLVM IR!
 * 
 * EXTRACT INSTRUCTIONS → CONVERT TO PACKET SHARDS → 1.3M CORES!
 */

#include "llvm_packet_compiler.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <assert.h>

// 🚀 LLVM IR PARSING STATE
typedef struct {
    char*    input;          // Input LLVM IR text
    size_t   input_len;      // Length of input
    size_t   pos;            // Current parse position
    uint32_t line;           // Current line number
    uint32_t instruction_id; // Unique instruction counter
    uint32_t block_id;       // Unique basic block counter
} llvm_parser_state_t;

// 💎 LLVM OPCODE STRING MAPPINGS
typedef struct {
    const char*   str;       // LLVM opcode string
    llvm_opcode_t opcode;    // Mapped opcode
} llvm_opcode_mapping_t;

static const llvm_opcode_mapping_t LLVM_OPCODE_MAP[] = {
    // Memory operations
    {"alloca", LLVM_ALLOCA},
    {"load", LLVM_LOAD},
    {"store", LLVM_STORE},
    {"getelementptr", LLVM_GEP},
    
    // Arithmetic operations
    {"add", LLVM_ADD},
    {"fadd", LLVM_FADD},
    {"sub", LLVM_SUB},
    {"fsub", LLVM_FSUB},
    {"mul", LLVM_MUL},
    {"fmul", LLVM_FMUL},
    {"udiv", LLVM_UDIV},
    {"sdiv", LLVM_SDIV},
    {"fdiv", LLVM_FDIV},
    {"urem", LLVM_UREM},
    {"srem", LLVM_SREM},
    {"frem", LLVM_FREM},
    
    // Bitwise operations
    {"shl", LLVM_SHL},
    {"lshr", LLVM_LSHR},
    {"ashr", LLVM_ASHR},
    {"and", LLVM_AND},
    {"or", LLVM_OR},
    {"xor", LLVM_XOR},
    
    // Conversion operations
    {"trunc", LLVM_TRUNC},
    {"zext", LLVM_ZEXT},
    {"sext", LLVM_SEXT},
    {"fptrunc", LLVM_FPTRUNC},
    {"fpext", LLVM_FPEXT},
    {"fptoui", LLVM_FPTOUI},
    {"fptosi", LLVM_FPTOSI},
    {"uitofp", LLVM_UITOFP},
    {"sitofp", LLVM_SITOFP},
    {"ptrtoint", LLVM_PTRTOINT},
    {"inttoptr", LLVM_INTTOPTR},
    {"bitcast", LLVM_BITCAST},
    
    // Comparison operations
    {"icmp", LLVM_ICMP},
    {"fcmp", LLVM_FCMP},
    
    // Control flow
    {"br", LLVM_BR},
    {"ret", LLVM_RET},
    {"call", LLVM_CALL},
    {"invoke", LLVM_INVOKE},
    {"switch", LLVM_SWITCH},
    
    // PHI and Select
    {"phi", LLVM_PHI},
    {"select", LLVM_SELECT},
    
    // Vector operations
    {"extractelement", LLVM_EXTRACTELEMENT},
    {"insertelement", LLVM_INSERTELEMENT},
    {"shufflevector", LLVM_SHUFFLEVECTOR},
    
    // Aggregate operations
    {"extractvalue", LLVM_EXTRACTVALUE},
    {"insertvalue", LLVM_INSERTVALUE},
    
    // Atomic operations
    {"cmpxchg", LLVM_CMPXCHG},
    {"atomicrmw", LLVM_ATOMICRMW},
    {"fence", LLVM_FENCE},
    
    {NULL, 0} // Sentinel
};

// 🔥 PARSER UTILITY FUNCTIONS

static void skip_whitespace(llvm_parser_state_t* state) {
    while (state->pos < state->input_len && 
           isspace(state->input[state->pos])) {
        if (state->input[state->pos] == '\n') {
            state->line++;
        }
        state->pos++;
    }
}

static void skip_comment(llvm_parser_state_t* state) {
    if (state->pos < state->input_len && state->input[state->pos] == ';') {
        // Skip to end of line
        while (state->pos < state->input_len && 
               state->input[state->pos] != '\n') {
            state->pos++;
        }
    }
}

static bool peek_char(llvm_parser_state_t* state, char c) {
    return (state->pos < state->input_len && 
            state->input[state->pos] == c);
}

static char consume_char(llvm_parser_state_t* state) {
    if (state->pos < state->input_len) {
        return state->input[state->pos++];
    }
    return '\0';
}

static bool parse_token(llvm_parser_state_t* state, char* token, size_t max_len) {
    skip_whitespace(state);
    skip_comment(state);
    skip_whitespace(state);
    
    size_t len = 0;
    while (state->pos < state->input_len && len < max_len - 1) {
        char c = state->input[state->pos];
        if (isspace(c) || c == ',' || c == ')' || c == '}') {
            break;
        }
        token[len++] = consume_char(state);
    }
    token[len] = '\0';
    return len > 0;
}

static llvm_opcode_t lookup_llvm_opcode(const char* str) {
    for (int i = 0; LLVM_OPCODE_MAP[i].str != NULL; i++) {
        if (strcmp(str, LLVM_OPCODE_MAP[i].str) == 0) {
            return LLVM_OPCODE_MAP[i].opcode;
        }
    }
    return 0; // Unknown opcode
}

// 🎯 MAIN PARSING FUNCTIONS

static bool parse_llvm_instruction(llvm_parser_state_t* state, 
                                 llvm_instruction_t* instruction) {
    char token[256];
    
    // Initialize instruction
    memset(instruction, 0, sizeof(llvm_instruction_t));
    instruction->instruction_id = state->instruction_id++;
    
    // Skip to next instruction
    skip_whitespace(state);
    skip_comment(state);
    
    if (state->pos >= state->input_len) {
        return false; // End of input
    }
    
    // Check for result register assignment (e.g., "%1 = add i32 %a, %b")
    if (peek_char(state, '%')) {
        if (!parse_token(state, instruction->result_reg, sizeof(instruction->result_reg))) {
            return false;
        }
        
        skip_whitespace(state);
        if (!peek_char(state, '=')) {
            return false;
        }
        consume_char(state); // consume '='
    }
    
    // Parse the opcode
    if (!parse_token(state, token, sizeof(token))) {
        return false;
    }
    
    instruction->opcode = lookup_llvm_opcode(token);
    if (instruction->opcode == 0) {
        LLVM_PACKET_LOG("Unknown LLVM opcode: %s (line %u)", token, state->line);
        // Continue parsing - might be a label or other construct
        return true;
    }
    
    // Parse type information (e.g., "i32", "ptr", "float")
    if (parse_token(state, instruction->type, sizeof(instruction->type))) {
        // Type parsed successfully
    }
    
    // Parse operands
    instruction->operand_count = 0;
    while (instruction->operand_count < 4 && 
           parse_token(state, token, sizeof(token))) {
        
        // Skip commas
        if (strcmp(token, ",") == 0) {
            continue;
        }
        
        // Check for end of instruction
        if (token[0] == '\n' || token[0] == ';') {
            break;
        }
        
        // Store operand
        strncpy(instruction->operands[instruction->operand_count], 
                token, sizeof(instruction->operands[0]));
        instruction->operand_count++;
    }
    
    LLVM_PACKET_LOG("Parsed instruction: %s %s (operands: %u)", 
                   token, instruction->type, instruction->operand_count);
    
    return true;
}

static bool parse_llvm_basic_block(llvm_parser_state_t* state, 
                                  llvm_basic_block_t* block) {
    char token[256];
    
    // Initialize basic block
    memset(block, 0, sizeof(llvm_basic_block_t));
    block->block_id = state->block_id++;
    
    // Parse basic block label
    skip_whitespace(state);
    if (parse_token(state, token, sizeof(token))) {
        if (token[strlen(token)-1] == ':') {
            // Remove trailing colon
            token[strlen(token)-1] = '\0';
            strncpy(block->label, token, sizeof(block->label));
            
            LLVM_PACKET_LOG("Found basic block: %s", block->label);
        }
    }
    
    // Parse instructions in this basic block
    uint32_t max_instructions = 256; // Start with reasonable limit
    block->instructions = malloc(sizeof(llvm_instruction_t) * max_instructions);
    if (!block->instructions) {
        return false;
    }
    
    while (state->pos < state->input_len) {
        // Check if we've hit another basic block or function end
        skip_whitespace(state);
        if (peek_char(state, '}') || peek_char(state, '\0')) {
            break;
        }
        
        // Look ahead for basic block label (ends with ':')
        size_t peek_pos = state->pos;
        bool found_label = false;
        while (peek_pos < state->input_len && 
               !isspace(state->input[peek_pos])) {
            if (state->input[peek_pos] == ':') {
                found_label = true;
                break;
            }
            peek_pos++;
        }
        if (found_label) {
            break; // Next basic block found
        }
        
        // Parse instruction
        if (block->inst_count >= max_instructions) {
            // Resize instruction array
            max_instructions *= 2;
            block->instructions = realloc(block->instructions, 
                                        sizeof(llvm_instruction_t) * max_instructions);
            if (!block->instructions) {
                return false;
            }
        }
        
        if (!parse_llvm_instruction(state, &block->instructions[block->inst_count])) {
            break;
        }
        
        block->instructions[block->inst_count].basic_block = block->block_id;
        block->inst_count++;
    }
    
    LLVM_PACKET_LOG("Basic block %s: %u instructions", 
                   block->label, block->inst_count);
    
    return true;
}

static bool parse_llvm_function(llvm_parser_state_t* state, 
                               llvm_function_t* function) {
    char token[256];
    
    // Initialize function
    memset(function, 0, sizeof(llvm_function_t));
    
    // Skip to function definition
    skip_whitespace(state);
    
    // Look for "define" keyword
    if (!parse_token(state, token, sizeof(token)) || 
        strcmp(token, "define") != 0) {
        return false;
    }
    
    // Parse return type
    if (!parse_token(state, function->return_type, sizeof(function->return_type))) {
        return false;
    }
    
    // Parse function name
    if (!parse_token(state, function->function_name, sizeof(function->function_name))) {
        return false;
    }
    
    // Skip parameter list for now (TODO: implement full parameter parsing)
    skip_whitespace(state);
    if (peek_char(state, '(')) {
        consume_char(state); // consume '('
        int paren_count = 1;
        while (state->pos < state->input_len && paren_count > 0) {
            char c = consume_char(state);
            if (c == '(') paren_count++;
            else if (c == ')') paren_count--;
        }
    }
    
    // Skip to function body
    skip_whitespace(state);
    if (!peek_char(state, '{')) {
        return false;
    }
    consume_char(state); // consume '{'
    
    LLVM_PACKET_LOG("Parsing function: %s %s", 
                   function->return_type, function->function_name);
    
    // Parse basic blocks
    uint32_t max_blocks = 64; // Start with reasonable limit
    function->basic_blocks = malloc(sizeof(llvm_basic_block_t) * max_blocks);
    if (!function->basic_blocks) {
        return false;
    }
    
    while (state->pos < state->input_len && !peek_char(state, '}')) {
        if (function->block_count >= max_blocks) {
            // Resize basic blocks array
            max_blocks *= 2;
            function->basic_blocks = realloc(function->basic_blocks, 
                                           sizeof(llvm_basic_block_t) * max_blocks);
            if (!function->basic_blocks) {
                return false;
            }
        }
        
        if (!parse_llvm_basic_block(state, &function->basic_blocks[function->block_count])) {
            break;
        }
        
        function->block_count++;
    }
    
    // Consume closing brace
    if (peek_char(state, '}')) {
        consume_char(state);
    }
    
    LLVM_PACKET_LOG("Function %s: %u basic blocks", 
                   function->function_name, function->block_count);
    
    return true;
}

// 🚀 PUBLIC API FUNCTIONS

int llvm_parse_ir_string(llvm_packet_compiler_t* compiler, const char* ir_text) {
    if (!compiler || !ir_text) {
        return -1;
    }
    
    // Initialize parser state
    llvm_parser_state_t state = {0};
    state.input = (char*)ir_text;
    state.input_len = strlen(ir_text);
    state.pos = 0;
    state.line = 1;
    state.instruction_id = 1;
    state.block_id = 1;
    
    // Initialize module
    compiler->module = malloc(sizeof(llvm_module_t));
    if (!compiler->module) {
        return -1;
    }
    memset(compiler->module, 0, sizeof(llvm_module_t));
    strncpy(compiler->module->module_name, "parsed_module", 
            sizeof(compiler->module->module_name));
    
    LLVM_PACKET_LOG("🚀 Starting LLVM IR parsing...");
    
    // Parse functions
    uint32_t max_functions = 32;
    compiler->module->functions = malloc(sizeof(llvm_function_t) * max_functions);
    if (!compiler->module->functions) {
        free(compiler->module);
        return -1;
    }
    
    while (state.pos < state.input_len) {
        if (compiler->module->function_count >= max_functions) {
            // Resize functions array
            max_functions *= 2;
            compiler->module->functions = realloc(compiler->module->functions, 
                                                sizeof(llvm_function_t) * max_functions);
            if (!compiler->module->functions) {
                return -1;
            }
        }
        
        if (!parse_llvm_function(&state, &compiler->module->functions[compiler->module->function_count])) {
            break;
        }
        
        compiler->module->function_count++;
    }
    
    LLVM_PACKET_LOG("✅ LLVM IR parsing complete!");
    LLVM_PACKET_LOG("   Module: %s", compiler->module->module_name);
    LLVM_PACKET_LOG("   Functions: %u", compiler->module->function_count);
    
    return 0;
}

int llvm_parse_ir_file(llvm_packet_compiler_t* compiler, const char* filename) {
    FILE* file = fopen(filename, "r");
    if (!file) {
        LLVM_PACKET_ERROR("Cannot open LLVM IR file: %s", filename);
        return -1;
    }
    
    // Get file size
    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    fseek(file, 0, SEEK_SET);
    
    // Read entire file
    char* ir_text = malloc(file_size + 1);
    if (!ir_text) {
        fclose(file);
        return -1;
    }
    
    fread(ir_text, 1, file_size, file);
    ir_text[file_size] = '\0';
    fclose(file);
    
    LLVM_PACKET_LOG("📁 Loaded LLVM IR file: %s (%ld bytes)", filename, file_size);
    
    // Parse the IR text
    int result = llvm_parse_ir_string(compiler, ir_text);
    free(ir_text);
    
    return result;
}

void llvm_print_module_info(llvm_module_t* module) {
    if (!module) return;
    
    printf("🚀 LLVM MODULE: %s\n", module->module_name);
    printf("   Functions: %u\n", module->function_count);
    printf("   Global variables: %u\n", module->global_count);
    
    for (uint32_t f = 0; f < module->function_count; f++) {
        llvm_function_t* func = &module->functions[f];
        printf("   📝 Function: %s %s\n", func->return_type, func->function_name);
        printf("      Basic blocks: %u\n", func->block_count);
        
        uint32_t total_instructions = 0;
        for (uint32_t b = 0; b < func->block_count; b++) {
            total_instructions += func->basic_blocks[b].inst_count;
        }
        printf("      Total instructions: %u\n", total_instructions);
        module->total_instructions += total_instructions;
    }
    
    printf("📊 TOTAL LLVM INSTRUCTIONS: %u\n", module->total_instructions);
}
