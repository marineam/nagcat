CREATE OR REPLACE PACKAGE pltest
IS
        PROCEDURE one (p_out    OUT     NUMBER);
        PROCEDURE two (p_in     IN      NUMBER,
                        p_out   OUT     NUMBER);
        PROCEDURE three (p_out  OUT     SYS_REFCURSOR);
        PROCEDURE four  (p_one  OUT     SYS_REFCURSOR,
                         p_two  OUT     SYS_REFCURSOR);
        PROCEDURE five (p_one   OUT     NUMBER,
                        p_two   OUT     NUMBER);

        PROCEDURE self_test(p_in_for_two        IN      NUMBER);
END pltest;
/
