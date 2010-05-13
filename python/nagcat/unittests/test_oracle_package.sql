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
END pltest;
/

CREATE OR REPLACE PACKAGE BODY pltest
IS
        PROCEDURE one (p_out    OUT     NUMBER)
        IS
        BEGIN
                SELECT 1 INTO p_out FROM dual;
        END one;
        PROCEDURE two (p_in     IN      NUMBER,
                        p_out   OUT     NUMBER)
        IS
        BEGIN
                p_out := MOD(1234567890,p_in);
        END two;
        PROCEDURE three (p_out  OUT     SYS_REFCURSOR)
        IS
        BEGIN
                OPEN p_out FOR
                SELECT LEVEL FROM dual
                CONNECT BY LEVEL <= 10;
        END three;
        PROCEDURE four  (p_one  OUT     SYS_REFCURSOR,
                         p_two  OUT     SYS_REFCURSOR)
        IS
        BEGIN
                OPEN p_one FOR
                SELECT LEVEL FROM dual
                CONNECT BY LEVEL <= 10;

                OPEN p_two FOR
                SELECT LEVEL FROM dual
                CONNECT BY LEVEL <= 10;
        END four;
        PROCEDURE five (p_one   OUT     NUMBER,
                        p_two   OUT     NUMBER)
        IS
        BEGIN
                p_one := 1;
                p_two := NULL;
        END five;
END pltest;
/
